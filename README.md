simple steam workshop downloader using steamcmd.

## USAGE

Download the release, extract and run "downloader.exe". Enter the app ID of the game (eg. `281990` for Stellaris) and one or more workshop IDs (the number in the URL of the mod), then press "Download".

The files will be downloaded to the `steamcmd/steamapps/workshop/content/<appID>/<workshop ID>` folder.

Right now, only single items are supported (no batch downloading of collections yet).

### WARNING

The first download can take several minutes, since steamcmd needs to download/update itself. After that, initiation of the download(s) should only take a few seconds.
