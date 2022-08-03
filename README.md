Simple steam workshop downloader using steamcmd.

List of supported games for anonymous download: https://steamdb.info/sub/17906/apps/

___

## USAGE

Download and run "downloader.exe". Enter one or more workshop URLs, then press "Download".

The files will be downloaded to the `steamcmd/steamapps/workshop/content/<appID>/<workshop ID>` folder (relative to the executable) by default.

Collections are also supported now.

### WARNING

The first download can take several minutes, since steamcmd needs to download/update itself. After that, initiation of the download(s) should only take a few seconds.
When downloading many and/or large items, the window might stop responding while the download is ongoing.

___

### CONFIGURATION

Open the downloader.ini file with any text editor and change or add the relevant values:

#### `[general]` section

- `steampath` : Location of the steamcmd.exe the program should use (either relative or absolute path)
- `theme` : Color scheme to use. Currently supported are 'default', 'sdark', 'solar, black' and 'white'.
- `batchsize` : Amount of items to download per batch. Low values cause a higher overhead when downloading many items (perhaps 5s per batch), while high values may cause issues on some systems. On Windows, the highest usable value seems to be about 700. Default is 50. Should be safe to increase to 500 in most cases.
- `login` : Steam username
- `passw` : Steam password
- `defaultpath` : moves all downloads with no other configured path to `<defaultpath>/<appid>`

If both `login` and `passw` are provided, it will try a non-anonymous login before downloading. When using 2FA, manual configuration of steamcmd might be neccassary.

#### `[appid]` sections

- `path` : Where downloaded mods for a certain game should be moved. Old versions of the mods in this location will be overwritten.

#### Example of a modified `downloader.ini`

```
[general]
steampath = steamcmd
theme = solar
batchsize = 500
login = user123
passw = 123456
defaultpath = mods

[281990]
# Stellaris
path = D:\games\stellaris\mods
```

___

### Non-anonymous downloads

To download items that require a steam account, you have to set the `login` and `passw` options in the `[general]` section.

In addition, if you are using SteamGuard, you will also need to authenticate the steamcmd installation to be able to download items with your account:
- If you never used the downloader before (or moved the `downloader.exe` to a new location), start the program and click `Download`. It will install steamcmd. Once it says `DONE`, you can close the window.
- Go to the folder containing `downloader.exe`, open the subfolder `steamcmd` and launch `steamcmd.exe`.
- Wait for it to finish updating (it will say `Steam>` when it's done), then enter `login <login>` with <login> being your username.
- Enter your password when it asks you for it. Your password will be invisible.
- Enter your SteamGuard code.
- If no errors appear, your installation is now authenticated.
- Enter `quit` to close steamcmd.
