simple steam workshop downloader using steamcmd.

## USAGE

Download the release, extract and run "downloader.exe". Enter the app ID of the game (see below) and one or more workshop IDs or URLs, then press "Download".

The files will be downloaded to the `steamcmd/steamapps/workshop/content/<appID>/<workshop ID>` folder.

Right now, only single items are supported (no batch downloading of collections yet).

### App ID

To find out the app ID of a game, go to its store page and look at the URL. The number after `/app/` is the app ID (eg. `https://store.steampowered.com/app/281990/Stellaris/` means the app ID of stellaris is 281990).

### WARNING

The first download can take several minutes, since steamcmd needs to download/update itself. After that, initiation of the download(s) should only take a few seconds.
