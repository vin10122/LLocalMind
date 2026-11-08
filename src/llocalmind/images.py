"""Local, metadata-free image copies and actual multimodal request content."""
from .i18n import tr
import base64
import hashlib
import io
import math
from pathlib import Path
import re
from .prompts import system_prompt,research_content
from collections import OrderedDict

MAX_IMAGES=4
MAX_BYTES=20*1024**2
IMAGE_PIXEL_LIMITS={"detail":None,"fast":512*512}


def validate_image_profile(profile):
    if not isinstance(profile,str) or profile not in IMAGE_PIXEL_LIMITS:raise ValueError("Invalid image profile")
    return profile


class ImagePayloadCache:
    """Bounded encoded-pixel cache, invalidated when a stored file changes."""
    def __init__(self,max_bytes=16*1024**2):
        self.max_bytes=max_bytes
        self.bytes=0
        self.entries=OrderedDict()

    def encode(self,path,item,profile="detail"):
        validate_image_profile(profile)
        info=path.stat()
        if info.st_size>MAX_BYTES:raise ValueError(tr('Immagine troppo grande'))
        key=(str(path.resolve()),item['id'],info.st_size,info.st_mtime_ns,info.st_ctime_ns,profile)
        if key in self.entries:
            self.entries.move_to_end(key)
            return self.entries[key]
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()+'.png'!=item['id']:
            raise ValueError(tr('Immagine salvata danneggiata'))
        limit=IMAGE_PIXEL_LIMITS[profile]
        if limit is not None:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as source:
                if source.width*source.height>32_000_000:
                    raise ValueError(tr('Usa PNG, JPEG o WebP fino a 32 megapixel'))
                if source.width*source.height>limit:
                    scale=math.sqrt(limit/(source.width*source.height))
                    size=(max(1,int(source.width*scale)),max(1,int(source.height*scale)))
                    source.thumbnail(size,Image.Resampling.LANCZOS,reducing_gap=2)
                    buffer=io.BytesIO()
                    source.save(buffer,format='PNG',compress_level=1)
                    data=buffer.getvalue()
        value='data:image/png;base64,'+base64.b64encode(data).decode('ascii')
        if len(value)<=self.max_bytes:
            while self.entries and self.bytes+len(value)>self.max_bytes:
                _,old=self.entries.popitem(last=False)
                self.bytes-=len(old)
            self.entries[key]=value
            self.bytes+=len(value)
        return value


def validate_images(images):
    if not isinstance(images,list) or len(images)>MAX_IMAGES:
        raise ValueError(tr('Massimo quattro immagini per messaggio'))
    for item in images:
        if (not isinstance(item,dict) or not isinstance(item.get('id'),str)
            or not re.fullmatch(r'[0-9a-f]{64}\.png',item['id'])
            or not isinstance(item.get('name'),str) or len(item['name'])>255):
            raise ValueError(tr('Riferimento immagine non valido'))
    return images


def image_path(directory,item):
    validate_images([item])
    path=Path(directory)/'images'/item['id']
    if path.is_symlink():raise ValueError(tr('Riferimento immagine non valido'))
    return path


def import_image(filename,directory):
    from PIL import Image,ImageOps
    filename=Path(filename)
    if not filename.is_file() or filename.stat().st_size>MAX_BYTES:
        raise ValueError(tr('Seleziona un’immagine locale di massimo 20 MiB'))
    with Image.open(filename) as source:
        if source.format not in ('PNG','JPEG','WEBP') or source.width*source.height>32_000_000:
            raise ValueError(tr('Usa PNG, JPEG o WebP fino a 32 megapixel'))
        # JPEG can decode at reduced resolution before allocating full pixels.
        source.draft('RGB',(2048,2048))
        oriented=ImageOps.exif_transpose(source)
        oriented.thumbnail((2048,2048))
        rgba=oriented.convert('RGBA')
        image=Image.new('RGB',rgba.size,'white')
        image.paste(rgba,mask=rgba.getchannel('A'))
        image.thumbnail((2048,2048))
        # Construct from pixels so EXIF, comments and profiles are not copied.
        image=Image.frombytes('RGB',image.size,image.tobytes())
        buffer=io.BytesIO()
        image.save(buffer,format='PNG')
    data=buffer.getvalue()
    if len(data)>MAX_BYTES:raise ValueError(tr('Immagine convertita troppo grande'))
    item=dict(id=hashlib.sha256(data).hexdigest()+'.png',name=filename.name[:255])
    path=image_path(directory,item)
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():path.write_bytes(data)
    return item


def chat_messages(messages,directory,*,cache=None,language='it',image_profile='detail',web_research=None):
    validate_image_profile(image_profile)
    if not messages or len(messages)%2!=1:
        raise ValueError(tr('La conversazione deve terminare con una domanda'))
    result=[dict(role='system',content=system_prompt(language,web_research))]
    cache=cache if cache is not None else ImagePayloadCache(max_bytes=0)
    for index,message in enumerate(messages):
        role='user' if index%2==0 else 'assistant'
        if (not isinstance(message,dict) or message.get('role')!=role
            or not isinstance(message.get('content'),str)):
            raise ValueError(tr('Ordine dei messaggi non valido'))
        images=validate_images(message.get('images',[]))
        content=message['content']
        if index==len(messages)-1:content=research_content(content,web_research,language)
        if images:
            if role!='user':raise ValueError('Immagini consentite solo nelle domande')
            content=[dict(type='text',text=content)]
            for item in images:
                path=image_path(directory,item)
                try:
                    encoded=cache.encode(path,item,profile=image_profile)
                except OSError as error:
                    raise ValueError(tr('Immagine non disponibile: ')+item['name']) from error
                content.append(dict(type='image_url',image_url=dict(url=encoded)))
        result.append(dict(role=role,content=content))
    return result
