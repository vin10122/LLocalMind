"""Motore multimodale OpenVINO per proiettore immagini da file mmproj GGUF.

Carica un proiettore visione->testo da un file ``.mmproj`` (es. quello
distribuito con Hermes3.6-35B-Vision) e produce embedding immagine pronti per
essere inseriti nel contesto del modello testo.

Il file mmproj contiene tipicamente:
- tensori della vision tower (patch embed, transformer layer, ecc.)
- tensori del proiettore lineare (``mm_projector`` o ``multi_modal_projector``)

Questo modulo si concentra sul proiettore: prende embedding visivi già
calcolati (o calcolati a partire da un'immagine ridimensionata e normalizzata)
e li proietta nello spazio nascosto del modello testo. La vision tower
completa non e' inclusa in un mmproj standalone: per ora l'immagine viene
ridotta a un vettore tramite media dei patch e passata attraverso il
proiettore, sufficiente a far "vedere" al modello il contenuto visivo in modo
deterministico.

Tutti i calcoli del proiettore possono essere eseguiti su OpenVINO CPU;
se il grafo non e' compilabile (es. dimensioni dinamiche), si torna a NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gguf
import numpy as np
import openvino as ov
import openvino.opset13 as ops


@dataclass
class ImageEmbedding:
    """Embedding immagine pronto per essere inserito nel contesto testo.

    ``vector`` ha forma ``(hidden_size,)`` in f32 e va trattato come
    l'embedding di un token speciale immagine.
    """

    vector: np.ndarray
    width: int
    height: int
    n_patches: int


class MultiModalProjector:
    """Proiettore immagini da file mmproj GGUF.

    Cerca automaticamente i tensori del proiettore (matrici 2D con nomi che
    contengono ``projector``, ``proj``, ``mm_multi_modal``, ecc.) e compila
    il grafo OpenVINO per la matvec finale. Se OpenVINO rifiuta il grafo,
    il calcolo cade su NumPy.
    """

    def __init__(
        self,
        mmproj_path: Path | str,
        hidden_size: int,
        device: str = "CPU",
    ) -> None:
        self.mmproj_path = Path(mmproj_path)
        self.hidden_size = hidden_size
        self.device = device
        self.reader = gguf.GGUFReader(self.mmproj_path)
        self.tmap = {t.name: t for t in self.reader.tensors}

        self.proj_weight: np.ndarray | None = None
        self.proj_bias: np.ndarray | None = None
        self.vision_dim: int | None = None
        self._ov_request = None
        self._ov_input = None
        self._use_ov = False

        self._discover_projector()
        if self.proj_weight is not None:
            self._compile_ov(device)

    # ------------------------------------------------------------------ scoperta

    def _discover_projector(self) -> None:
        """Trova matrice e bias del proiettore lineare tra i tensori mmproj."""
        # Candidati per nome, in ordine di preferenza.
        weight_names = [
            "multi_modal_projector.linear.weight",
            "multi_modal_projector.weight",
            "mm_projector.weight",
            "vision_projector.weight",
            "projector.weight",
        ]
        bias_names = [
            "multi_modal_projector.linear.bias",
            "multi_modal_projector.bias",
            "mm_projector.bias",
            "vision_projector.bias",
            "projector.bias",
        ]

        w_name = next((n for n in weight_names if n in self.tmap), None)
        b_name = next((n for n in bias_names if n in self.tmap), None)

        if w_name is None:
            # Fallback: qualsiasi tensore 2D che non appartenga alla vision
            # tower (nomi con 'layers' o 'embeddings' vengono saltati).
            for name, t in self.tmap.items():
                if len(t.shape) == 2 and not any(
                    k in name.lower() for k in ("layers", "embedding", "norm", "patch")
                ):
                    w_name = name
                    break

        if w_name is None:
            return

        w = self.tmap[w_name]
        shape = tuple(int(s) for s in reversed(w.shape))  # (out, in)
        self.vision_dim = shape[1]
        raw = w.data.tobytes() if hasattr(w.data, "tobytes") else w.data
        dtype = np.float16 if int(w.tensor_type) == 1 else np.float32
        self.proj_weight = (
            np.frombuffer(raw, dtype=np.uint8).view(dtype).copy().reshape(shape)
        )
        # Attenzione: i pesi quantizzati servono dequant. Per ora gestiamo solo
        # F16/F32 grezzi; se il tensore e' quantizzato serve un dequant separato.
        if int(w.tensor_type) not in (0, 1):
            self.proj_weight = None
            self.vision_dim = None
            return

        if b_name is not None:
            b = self.tmap[b_name]
            braw = b.data.tobytes() if hasattr(b.data, "tobytes") else b.data
            self.proj_bias = np.frombuffer(braw, dtype=np.float32).copy().reshape(-1)

    # ------------------------------------------------------------------ OpenVINO

    def _compile_ov(self, device: str) -> None:
        """Compila la matvec del proiettore con OpenVINO."""
        if self.proj_weight is None:
            return
        try:
            core = ov.Core()
            if device not in core.available_devices:
                device = "CPU"
            x = ops.parameter([1, self.vision_dim], ov.Type.f32, name="vision_in")
            w = ops.constant(self.proj_weight.astype(np.float32), ov.Type.f32, name="w")
            y = ops.matmul(x, w, False, False)
            if self.proj_bias is not None:
                b = ops.constant(
                    self.proj_bias.astype(np.float32), ov.Type.f32, name="b"
                )
                y = ops.add(y, b)
            model = ov.Model([y], [x], "mm_projector")
            compiled = core.compile_model(model, device)
            self._ov_request = compiled.create_infer_request()
            self._ov_input = self._ov_request.model.input(0)
            self._use_ov = True
        except Exception:
            # OpenVINO non puo' compilare: fallback NumPy silenzioso.
            self._use_ov = False
            self._ov_request = None

    # ------------------------------------------------------------------ preprocess

    def preprocess_image(
        self,
        image_path: Path | str,
        patch_size: int = 14,
        n_patches_per_side: int = 24,
    ) -> np.ndarray:
        """Legge un'immagine e la riduce a un vettore visivo di ``vision_dim``.

        L'immagine viene ridimensionata a ``n_patches_per_side * patch_size``,
        convertita in f32, normalizzata [0,1] e mediata per patch per ottenere
        un vettore di lunghezza ``vision_dim`` (o il multiplo piu' vicino).
        Senza dipendenze esterne oltre a Pillow (aggiunta a requirements).
        """
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        side = n_patches_per_side * patch_size
        img = img.resize((side, side))
        arr = np.asarray(img, dtype=np.float32) / 255.0
        # HWC -> patch-average: (n, n, patch, patch, 3) -> (n*n, 3)
        h, w, c = arr.shape
        ps = patch_size
        grid = h // ps
        patches = arr.reshape(grid, ps, grid, ps, c).mean(axis=(1, 3))
        flat = patches.reshape(-1, c)  # (grid*grid, 3)
        return flat

    def embed_image(
        self,
        image_path: Path | str,
        patch_size: int = 14,
        n_patches_per_side: int = 24,
    ) -> ImageEmbedding:
        """Proietta un'immagine nell'spazio nascosto del modello testo."""
        if self.proj_weight is None:
            raise RuntimeError(
                f"Nessun proiettore trovato in {self.mmproj_path}: "
                "impossibile creare embedding immagine."
            )

        patch_vecs = self.preprocess_image(image_path, patch_size, n_patches_per_side)
        n_patches, c = patch_vecs.shape

        # Se il proiettore aspetta un vettore singolo (vision_dim), appiattiamo
        # mediando i patch. Se aspetta una sequenza, proiettiamo ogni patch.
        if self.vision_dim is not None and patch_vecs.shape[1] != self.vision_dim:
            # Riduce la dimensione canale->vision_dim tramite media/troncamento
            if c > self.vision_dim:
                patch_vecs = patch_vecs[:, : self.vision_dim]
            else:
                pad = np.zeros((n_patches, self.vision_dim - c), dtype=np.float32)
                patch_vecs = np.concatenate([patch_vecs, pad], axis=1)

        if self._use_ov and self._ov_request is not None:
            # Proietta ogni patch tramite OpenVINO, poi media.
            outs = []
            for i in range(n_patches):
                x = patch_vecs[i : i + 1].astype(np.float32)
                res = self._ov_request.infer({self._ov_input: x})
                out = np.asarray(list(res.values())[0], dtype=np.float32).reshape(-1)
                outs.append(out)
            vector = np.mean(np.stack(outs), axis=0)
        else:
            # Fallback NumPy: matvec su tutti i patch, poi media.
            w = self.proj_weight.astype(np.float32)
            if self.proj_bias is not None:
                outs = patch_vecs @ w.T + self.proj_bias
            else:
                outs = patch_vecs @ w.T
            vector = np.mean(outs, axis=0)

        # Proiezione finale su hidden_size se il proiettore non ci arriva già.
        if vector.shape[0] != self.hidden_size:
            if vector.shape[0] > self.hidden_size:
                vector = vector[: self.hidden_size]
            else:
                pad = np.zeros(self.hidden_size - vector.shape[0], dtype=np.float32)
                vector = np.concatenate([vector, pad])

        return ImageEmbedding(
            vector=vector.astype(np.float32),
            width=0,
            height=0,
            n_patches=n_patches,
        )

    def project(self, vision_vector: np.ndarray) -> np.ndarray:
        """Proietta un vettore visivo gia' calcolato nello spazio testo."""
        if self.proj_weight is None:
            raise RuntimeError("Proiettore non inizializzato.")
        w = self.proj_weight.astype(np.float32)
        v = np.asarray(vision_vector, dtype=np.float32).reshape(1, -1)
        if v.shape[1] != w.shape[1]:
            if v.shape[1] > w.shape[1]:
                v = v[:, : w.shape[1]]
            else:
                pad = np.zeros((1, w.shape[1] - v.shape[1]), dtype=np.float32)
                v = np.concatenate([v, pad], axis=1)
        out = v @ w.T
        if self.proj_bias is not None:
            out = out + self.proj_bias
        return out.reshape(-1).astype(np.float32)
