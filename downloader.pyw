import subprocess
from winpty import PTY # real time communication
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import re
import requests
import concurrent.futures
import configparser
import os
import shutil
import math
import time
from zipfile import ZipFile
from io import BytesIO
from urllib.parse import unquote
from functools import partial

# for async IO
from threading import Thread
from queue import Queue, Empty

baseurl = "https://steamcommunity.com/sharedfiles/filedetails/?id="


## utility functions
def modpath(base, appid, wid):
    return os.path.join(base,'steamapps/workshop/content/',str(appid),str(wid))

def getDirSize(path):
    return sum([e.stat().st_size for e in os.scandir(path)])

def sizeAsBytes(string):
    a,b = string.split()
    mult = {'B': 1, 'KB': 10**3, 'MB': 10**6, 'GB': 10**9, 'TB': 10**12}
    return int(float(a)*mult.get(b,1))

def bytesAsSize(num):
    mult = {'B': 1, 'KB': 10**3, 'MB': 10**6, 'GB': 10**9, 'TB': 10**12}
    for suffix, val in mult.items():
        if num <= 1000*val: break
    num /= val
    digits = max(2-math.floor(math.log(num, 10)),0)
    num = round(num, digits)
    if(digits==0): num = int(num)
    return str(num)+suffix


# threading
def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
        out.close()
 
def enqueue_output2(out, queue): # todo
    buffer = ""
    time = time.time()
    while True:
        pass

## options, stateful behavior
def update_steamdb(old_ids, show_warnings = False):
    # currently indirection over gist, to prevent captcha issues
    #page = requests.get("https://steamdb.info/sub/17906/apps/")
    #matches = re.findall('href="(\d+)',page.text)
    try:
        page = requests.get("https://gist.githubusercontent.com/shadoxxhd/b9f57b5a729525346e01c54e3442e21c/raw/d6dcda892b7336d58f2b2b8012034a3fb19fe45f/gistfile1.txt")
        new_ids = list(map(int,page.text.split()))
        changed = False
        if(new_ids != old_ids):
            log("appid database updated")
            changed = True
        return (new_ids, changed)
    except Exception as e:
        if show_warnings:
            log("couldn't get appid gist: {e}")
        return (old_ids, False)



class Options:
    # main
    theme: str = "default"
    steampath: str = "steamcmd"
    defaultpath: str = "mods"
    batchsize: int = 50
    # login
    login: str = None
    passw: str = None
    steamguard: bool = True
    # behavior
    getDetails: bool = True
    showConsole: bool = False
    show_warnings: bool = False
    steamdb: bool = True
    steamdb_date: int = 0
    anon_ids: list = []

    # other stuff
    cfg: configparser.ConfigParser = None
    volatile: bool = False # not an option, but a flag indicating if UI needs to be rebuilt

    def __init__(self, cfg):
        if cfg is None: raise ValueError("no configParser object passed")
        self.cfg = cfg
        if 'general' in cfg:
            general = cfg['general']
            if 'theme' in general:
                self.theme = general['theme']
            if 'steampath' in general:
                self.steampath = general['steampath']
            if 'batchsize' in general:
                self.batchsize = cfg.getint('general','batchsize')
            if 'defaultpath' in general:
                self.defaultpath = general['defaultpath']
            if 'login' in general:
                self.login = general['login']
            if 'passw' in general:
                self.passw = general['passw']
            if 'steamguard' in general:
                self.steamguard = cfg.getboolean('general','steamguard')
            if 'getDetails' in general:
                self.getDetails = cfg.getboolean('general', 'getDetails')
            if 'showConsole' in general:
                self.showConsole = cfg.getboolean('general','showConsole')
            if 'show_warnings' in general:
                self.show_warnings = cfg.getboolean('general', 'show_warnings')
            if 'steamdb' in general:
                self.steamdb = cfg.getboolean('general', 'steamdb')
            if 'steamdb_date' in general:
                self.steamdb_date = cfg.getint('general', 'steamdb_date')
        else:
            cfg.add_section('general')


    def postinit(self):
        if self.steamdb and os.path.exists("appids.db"):
            with open("appids.db", "r") as f:
                for line in f:
                    self.anon_ids.append(int(line))
        if self.steamdb and (not os.path.exists("appids.db") or time.time()-self.steamdb_date > 3600): # more than an hour since the last update
            self.anon_ids, changed = update_steamdb(self.anon_ids, self.show_warnings)
            if changed:
                with open("appids.db", "w") as f:
                    f.write("\n".join(map(str,self.anon_ids)))
            self.steamdb_date = int(time.time()) # delay next check even if unsuccessful, for faster startup
            self.write()

    def setOption(self, name, value):
        setattr(self, name, value)
        self.cfg.set('general', name, str(value))
        if name in ['theme', 'steamguard']:
            self.volatile = True

    def write(self): # returns if application will be restarted
        # write config to file
        with open('downloader.ini', 'w') as file:
            self.cfg.write(file)
        if self.volatile:
            global restart
            global URLinput
            global output
            global root
            restart = (URLinput.get("1.0", tk.END), output.get("1.0", tk.END))
            #print(restart)
            root.destroy()
            return True
        return False

## UI
def log(data, newline = True, update = True):
    global output
    global logfile

    if logfile:
        logfile.write(str(data)+("\n" if newline else ""))

    if not output:
        return
    output.config(state='normal')
    output.insert(tk.END,str(data)+("\n" if newline else ""))
    output.config(state='disabled')
    if(update):
        output.see(tk.END)
        output.update()

def logException(ex, newline = True, update = True):
    log(f"{type(ex)}: {ex} (line {ex.__traceback__.tb_lineno})", newline, update)

# validator for input fields
def validate(val, conv):
    try:
        x = conv(val)
        return True
    except ValueError:
        return False


def optionsDialog(options):
    global root
    global button1
    global running
    # cancel if download is running
    if running:
        log("wait until the current task is finished")
        return
    # prevent starting download
    button1.state = tk.DISABLED
    running = True

    # create options window
    w_options = tk.Toplevel(root)
    w_options.title = "Options"
    # define close handler
    def optionsDialogClose(save=None):
        global button1
        global running
        global restart
        if save is None:
            # todo: check for changes
            for k,v in design.items():
                newval = v[4](v[5].get())
                if newval != getattr(options, k):
                    break
            else:
                save = False
            if save is None: save = messagebox.askyesnocancel("Save", "Save changes?")
        if save:
            # todo: save changes to options
            changed = False
            for k,v in design.items():
                newval = v[4](v[5].get())
                if newval != getattr(options, k):
                    log(f"{k} set to {newval}")
                    #setattr(options, k, newval)
                    options.setOption(k, newval)
                    changed = True
            if changed:
                if options.write():
                    running = False
                    return
        elif save is None: # 'X' button, then 'cancel'
            return
        else: # cancel
            pass
        running = False
        button1.state=tk.NORMAL
        w_options.destroy()

    w_options.protocol("WM_DELETE_WINDOW", optionsDialogClose)
    # each element is a list of: UI text/type/argument list/config lambdas array/type converter/var iff Checkbutton or Combobox, otherwise element
    # the dict keys are also the option accessors (options.__dict__[accessor]=...)
    ttk_boolconfig = [lambda cb: cb.state(['!alterante']), lambda cb: cb.state([('' if options.steamguard else '!')+'selected'])]
    boolconfig = []
    design = {
        'theme': ['Theme',ttk.Combobox, {"state":"readonly", "values":["default", "sdark", "solar", "black", "white"], "textvariable": (tmp:=tk.StringVar())}, [], lambda x: x, tmp],
        'steampath': ['path to steamcmd', tk.Entry, {"width":25}, [], lambda x:x],
        'defaultpath': ['default mod path', tk.Entry, {"width":25}, [], lambda x: x],
        'batchsize': ['items per batch', tk.Spinbox, {"width":20, "from_": 1, "to": 2000, "textvariable": (tmp:=tk.IntVar())}, [], int, tmp], #"validate": 'key', "validatecommand": (root.register(partial(validate, conv=int)), '%P')
        'login': ['login', tk.Entry, {"width":25}, [], lambda x: x],
        'passw': ['password', tk.Entry, {"width":25}, [], lambda x:x],
        'steamguard': ['steamguard', tk.Checkbutton, {"variable":(tmp:=tk.IntVar())}, boolconfig, lambda x:x, tmp],
        'show_warnings': ['show warnings', tk.Checkbutton, {"variable":(tmp:=tk.IntVar())}, boolconfig, lambda x:x, tmp],
        'steamdb': ['check anonymous appid', tk.Checkbutton, {"variable":(tmp:=tk.IntVar())}, boolconfig, lambda x:x, tmp]
    }
    # warning: bool options need .instate(['selected']) instead of .get !!
    #  or .var.get in case of tk.Checkbutton
    # lambda x:x.bind('<<ComboboxSelected>>', partial(options.setOption,'theme'))
    i = 0
    for k,v in design.items():
        #row = tk.Frame(w_options, width=60)
        #row.pack(padx=0, pady=1, side=tk.TOP, fill=tk.X)
        lb = tk.Label(w_options, text=v[0])
        #lb.pack(side=tk.LEFT, expand=0, fill=tk.X)
        lb.grid(row = i, column = 0, sticky = tk.W, pady=3)
        el = v[1](w_options, **v[2])
        #el.pack(side=tk.RIGHT, expand=0)
        el.grid(row = i, column = 1, sticky=tk.E, padx=3)
        i+=1
        v.append(el)
        # set default state
        if isinstance(el, tk.Spinbox) or isinstance(el, tk.Checkbutton):
            v[5].set(getattr(options,k))
        elif isinstance(el, ttk.Combobox):
            v[5].set(str(getattr(options,k)))
        elif isinstance(el, tk.Entry):
            el.insert(0, str(getattr(options,k)))
    #row = tk.Frame(w_options)
    #row.pack(padx=0, pady=1, side=tk.TOP, fill=tk.X)
    cancel = tk.Button(w_options, text="Cancel", command=partial(optionsDialogClose, save=False))
    #cancel.pack(side=tk.LEFT, expand=1)
    cancel.grid(row=i, column=0, pady=3)
    save = tk.Button(w_options, text="Save", command=partial(optionsDialogClose, save=True))
    #save.pack(side=tk.LEFT, expand=1)
    save.grid(row=i, column=1)

    #w_options.update()
    #w_options.transient(root)
    w_options.grab_set()
    w_options.focus_force()
    w_options.lift()
    root.wait_window(w_options)

## download functionality

# asynchronous requests

def getDetails(wid):
    try:
        y = requests.get(baseurl+wid)
        size = sizeAsBytes(re.findall(r'detailsStatRight">([\d\. KMGTB]+)', y.text)[0])
        name = unquote(re.findall(r'workshopItemTitle">([^<]*)<', y.text)[0])
        return wid, size, name
    except:
        return wid, 0, None


def getWidData(wids):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = (executor.submit(getDetails, wid) for wid in wids)
        for future in concurrent.futures.as_completed(futures):
            try:
                wid, size, name = future.result()
                if(name is not None):
                    results[wid] = (size, name)
                    log(f"{name}: {bytesAsSize(size)}")
                else:
                    results[wid] = (-1, str(wid)) # placeholder values
            except Exception as exc:
                log(f"{type(exc)} - {exc}")
    return results


# faster download when mixing games
def getWids(text):
    global options
    download = []
    appids = set()
    totalsize = 0
    for line in text.splitlines():
        if len(line)>0:
            # check for collection
            try:
                wid = re.match("(?>[^\\d]*)(\\d+)",line)[1]
                #x = requests.get(line)
                x = requests.get(baseurl+wid)
            except Exception as exc:
                log("Couldn't get workshop page for "+line)
                log(type(exc))
                log(exc)
            else: 
                if re.search("SubscribeCollectionItem",x.text):
                    # collection
                    dls = re.findall(r"SubscribeCollectionItem[\( ']+(\d+)[ ',]+(\d+)'",x.text)
                    try:
                        if options.getDetails:
                            details = getWidData([dl[0] for dl in dls])
                        for wid, appid in dls:
                            size = -1
                            name = str(wid)
                            if options.getDetails:
                                size, name = details[wid]
                                totalsize += size
                            download.append((appid,wid,name,size)) # appid, wid, name, size
                            appids.add(int(appid))
                        #print("download list populated")
                    except Exception as ex:
                        logException(ex)
                elif re.search("ShowAddToCollection",x.text):
                    # single item
                    wid, appid = re.findall(r"ShowAddToCollection[\( ']+(\d+)[ ',]+(\d+)'",x.text)[0]
                    size = sizeAsBytes(re.findall(r'detailsStatRight">([\d\. KMGTB]+)', x.text)[0])
                    name = unquote(re.findall(r'workshopItemTitle">([^<]*)<', x.text)[0])
                    if options.getDetails:
                        log(f"{name}: {bytesAsSize(size)}")
                    download.append((appid,wid,name,size))
                    appids.add(int(appid))
                    totalsize += size
                else:
                    log('"'+line+'" doesn\'t look like a valid workshop item...\n')
                if(options.getDetails):
                    log(f"total download size: {bytesAsSize(totalsize)}")
    return (download, totalsize, appids)

def download():
    # don't start multiple steamcmd instances
    global running
    global options # cached cfg items
    global URLinput
    global button1
    global output
    global SGinput

    global logfile
    debug = False
    
    if running:
        return
    button1.state = tk.DISABLED
    running = True
    try:
        # check if steamcmd exists
        if not os.path.exists(os.path.join(options.steampath,"steamcmd.exe")):
            log("Installing steamcmd ...",0)
            
            # get it from steam servers
            resp = requests.get("https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip")
            ZipFile(BytesIO(resp.content)).extractall(options.steampath)
            log(" DONE")
        # get array of IDs
        download, totalsize, appids = getWids(URLinput.get("1.0",tk.END))

        # build dict to reference later
        data = {}
        for appid, wid, name, size in download:
            data[wid] = (appid, name, size)

        anonymous = options.login is None or options.login == "" or options.passw is None or options.passw == ""
        if(options.steamdb and anonymous and options.anon_ids):
            flag = 0
            for appid in appids:
                if appid not in options.anon_ids:
                    log(f"{appid} is not known to support anonymous downloads. ")
                    flag = 1
            if flag:
                log("You might need to log into a steam account that owns the games in question to successfully download workshop items.")

        l = len(download)
        lim = options.batchsize

        sgcode = None
        if options.steamguard:
            sgcode = SGinput.get()

        errors = {}
        status = {}
        fails = 0
        success = 0
        
        for i in range(math.ceil(l/lim)):
        #for appid in download:
            batch = download[i*lim:min((i+1)*lim,l)]
            
            # assemble command line
            args = [os.path.join(options.steampath,'steamcmd.exe')]
            #if options.login is not None and options.login != "" and options.passw is not None:
            if not anonymous:
                args.append('+login '+options.login+' '+options.passw+(' '+sgcode if options.steamguard and len(sgcode)>0 else ''))
            #elif options.login is not None:
            #    args.append('+login '+options.login)
            else:
                args.append('+login anonymous')
            for appid, wid, name, size in batch:
                args.append(f'+workshop_download_item {appid} {int(wid)}')
            args.append("+quit")

            if debug:
                print(args)
            
            process = PTY(500,25)
            process.spawn(" ".join(args))
            
            while(not process.iseof()):
                try:
                    line = process.read().strip()
                    if line=="":
                        continue
                    if line[:8] == "Download":
                        wid = re.match("(?>[^\\d]*)(\\d+)", line)[1]
                        log(f"Downloading {data[wid][1]} ...")
                        status[wid] = 1
                    if line[:8] == "Success.":
                        wid = re.match("(?>[^\\d]*)(\\d+)", line)[1]
                        status[wid] = 2 # success
                        log(f"{data[wid][1]} successfully downloaded ({bytesAsSize(data[wid][2])})")
                        success += 1
                    if line[:5] == "ERROR":
                        wid = re.match("(?>[^\\d]*)(\\d+)", line)[1]
                        reason = re.search("\\(([^\\)]+)\\)", line)[1]
                        status[wid] = 3 # error
                        errors[wid] = reason
                        log(f"Error downloading {data[wid][1]} ({reason}).")
                        if(options.steamdb and anonymous and options.anon_ids):
                            if(int(appid) not in options.anon_ids):
                                log(f"The corresponding game isn't known to allow anonymous downloads. You might need to use an account that owns that game.")
                        fails += 1
                    logfile.write("> "+line+"\n")
                except Exception as ex:
                    # expected EOF error
                    pass

            # move mods
            pc = {} # path cache
            for appid, wid, name, size in batch:
                if wid not in status:
                    errors[wid]="no record"
                elif status[wid] == 1: # "still downloading" -> makes no sense
                    pass # TODO
                elif status[wid] != 2: # download not successful
                    continue
                if appid in pc or options.cfg.get(str(appid),'path',fallback=None) or options.defaultpath:
                    path = pc.get(appid,options.cfg.get(str(appid),'path',
                                    fallback = options.defaultpath and os.path.join(options.defaultpath,str(appid))))
                    if os.path.exists(modpath(options.steampath,appid,wid)):
                        # download was successful
                        log("Moving "+str(wid)+" to "+path+" ...",0)
                        if(os.path.exists(os.path.join(path,str(wid)))):
                            # already exists -> delete old version
                            shutil.rmtree(os.path.join(path,str(wid)))
                        shutil.move(modpath(options.steampath,appid,wid),os.path.join(path,str(wid)))
                        log(" DONE")
                    pc[appid]=path
        # reset input, then add back errored items to try again
        URLinput.delete("1.0", tk.END)
        for wid in errors:
            URLinput.insert(tk.END, wid+"\n")

        # print stats
        log(f"downloaded {success} out of {success+fails} requested items")
        if len(errors) > 0:
            log(f"failed items have been added back to the input field")

    except Exception as ex:
        logException(ex)
    finally:
        button1.state = tk.NORMAL
        running = False


def main():
    global options
    global root
    global button1
    global URLinput
    global output
    global SGinput

    global logfile

    global running
    global restart
    restart = False
    running = False
    
    logfile = open("downloader.log", "w")

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read('downloader.ini')

    options = Options(cfg)

    while True:

        padx = 3
        pady = 3
        
        theme = options.theme
        if theme=='sdark':
            # Solarized dark
            bg1="#002b36"
            bg2="#073642"
            textcol="#b58900"
        elif theme=='solar':
            # Solarized
            bg1="#fdf6e3"
            bg2="#eee8d5"
            textcol="#073642"
        elif theme=='black':
            bg1="#333"
            bg2="#555"
            textcol="#eee"
        elif theme=='white':
            bg1="#e8e8e8"
            bg2="#e8e8e8" 
            textcol="#000000"
            pass
        elif theme=='default':
            bg1=None
            bg2=None
            textcol=None
        else:
            log("invalid theme specified")
            bg1=None
            bg2=None
            textcol=None
        
        # create UI
        root = tk.Tk()
        root['bg'] = bg1
        root.title("Steam Workshop Downloader")
        
        frame = tk.Frame(root, bg=bg1)
        frame.pack(padx=0,pady=0,side=tk.LEFT, fill=tk.Y)
        
        labelURLi = tk.Label(frame, text='Workshop URLs', fg=textcol, bg=bg1)
        labelURLi.pack(padx=padx,pady=pady,side=tk.TOP)
        
        URLinput = tk.Text(frame, width = 67, height = 20, fg=textcol, bg=bg2) # root
        URLinput.pack(padx=padx,pady=pady,side=tk.TOP, expand=1, fill=tk.Y)
        URLinput.bind("<Button-3>", lambda a: URLinput.insert(tk.END,root.clipboard_get()+"\n"))
        if restart:
            URLinput.insert("1.0", restart[0])
        
        button1 = tk.Button(frame, text='Download', command=download, fg=textcol, bg=bg1) # root
        button1.pack(padx=padx,pady=pady,side=tk.LEFT, fill=tk.X, expand=1)

        button2 = tk.Button(frame, text="⚙", command=partial(optionsDialog,options=options), fg=textcol, bg=bg1)
        button2.pack(padx=padx, pady=pady, side=tk.LEFT)
        
        output = tk.Text(root, width=56, height = 20, fg=textcol, bg=button1['bg'], font=("Consolas",10), state="disabled")
        output.pack(padx=padx,pady=pady,side=tk.BOTTOM,fill=tk.BOTH,expand=1)
        if restart:
            log(restart[1])
        restart = False

        if(options.steamguard):
            SGlabel = tk.Label(root, text="SteamGuard Code", fg=textcol, bg=bg1)
            SGlabel.pack(padx=padx, pady=pady, side=tk.LEFT, expand=0, fill=tk.X)

            SGinput = tk.Entry(root, width=5, fg=textcol,bg=bg2)
            SGinput.pack(padx=padx, pady=pady, side=tk.LEFT, expand=1, fill=tk.X)
        
        # load secondary configs etc.
        options.postinit()

        root.mainloop()

        if not restart:
            break
    
    if not os.path.exists('downloader.ini'):
        options.write()

if __name__ == '__main__':
    global restart

    main()
