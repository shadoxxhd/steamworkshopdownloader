pyinstaller --onefile downloader.py
rm release/downloader.exe
mv dist/downloader.exe release/downloader.exe
