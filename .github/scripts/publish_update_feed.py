"""CI: publish a bounded official fallback feed after complete release uploads."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from llocalmind.updater import REPOSITORY,UpdateError,UpdateManager,version_tuple


def build_feed(releases,required_tag):
    result=[]
    for release in releases:
        if not isinstance(release,dict) or release.get('draft'):continue
        try:
            version_tuple(release.get('tag_name'))
            raw=json.dumps([release]).encode()
            validated=UpdateManager('0.0.0',opener=lambda *a,**kw:io.BytesIO(raw)).check()
        except UpdateError:continue
        if validated is None:continue
        names={validated.asset_name,validated.asset_name+'.sha256'}
        assets=[{key:asset[key] for key in ('name','browser_download_url','size','digest') if key in asset}
                for asset in release['assets'] if asset.get('name') in names]
        result.append(dict(tag_name=validated.tag,draft=False,prerelease=validated.prerelease,
            name=validated.name[:300],body=validated.notes[:4000],assets=assets))
    if required_tag not in {r['tag_name'] for r in result}:
        raise RuntimeError('Requested release is missing or its installer/checksum is incomplete')
    feed=dict(schema=1,releases=result)
    if len(json.dumps(feed).encode())>2*1024**2:raise RuntimeError('Update feed too large')
    return feed


def main():
    repo=os.environ['GH_REPO']
    if repo!=REPOSITORY:raise RuntimeError('Unexpected release repository')
    tag=os.environ['RELEASE_TAG']
    path='.github/update-feed.json'
    for attempt in range(3):
        # Read the file revision before listing releases. On concurrent writes,
        # regenerate from a fresh API response rather than overwriting new data.
        previous=subprocess.run(['gh','api',f'repos/{repo}/contents/{path}?ref=master'],capture_output=True,text=True)
        releases=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases?per_page=100']))
        try:feed=build_feed(releases,tag)
        except RuntimeError:
            if attempt==2:raise
            time.sleep(attempt+1)
            continue
        payload=dict(message=f'Publish official update feed for {tag}',branch='master',
            content=base64.b64encode((json.dumps(feed,indent=2)+'\n').encode()).decode())
        if previous.returncode==0:payload['sha']=json.loads(previous.stdout)['sha']
        result=subprocess.run(['gh','api','--method','PUT',f'repos/{repo}/contents/{path}','--input','-'],
            input=json.dumps(payload).encode(),capture_output=True)
        if result.returncode==0:
            print(f'Official fallback feed published: {tag}, {len(feed["releases"])} complete releases')
            return
        if attempt==2:raise RuntimeError('Could not publish update feed: '+result.stderr.decode(errors='replace')[-500:])
        time.sleep(attempt+1)


if __name__=='__main__':main()
