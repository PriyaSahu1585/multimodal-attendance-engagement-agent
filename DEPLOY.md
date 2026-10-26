# How to put this app online — complete beginner guide

You will use two free websites:
- **GitHub** — stores your project files online (like Google Drive for code).
- **Streamlit Community Cloud** — runs the app and gives you a public link.

No coding or command line needed. Takes about 15 minutes.

---

## Part A — Run it on your own computer first (optional but recommended)

1. Install **Python 3.11** from https://www.python.org/downloads/ .
   On Windows, **tick "Add Python to PATH"** on the first install screen.
2. Unzip this project. Open the folder that contains `app.py`.
3. Windows: click the folder's address bar, type `cmd`, press Enter. (Mac: right-click folder → "New Terminal at Folder".)
4. Type these one at a time, pressing Enter after each:
   ```
   python -m venv .venv
   .venv\Scripts\activate          (Mac: source .venv/bin/activate)
   pip install -r requirements.txt
   streamlit run app.py
   ```
5. Your browser opens the app. Press `Ctrl + C` in the black window to stop it.

---

## Part B — Put your files on GitHub

1. Go to https://github.com/signup and create a free account (verify your email).
2. After logging in, click the **+** icon (top right) → **New repository**.
3. Repository name: `attendance-engagement-agent`. Choose **Public**. Click **Create repository**.
4. On the next page, click the link **"uploading an existing file"**.
5. Open the unzipped project folder on your computer, select **everything inside it**
   (`app.py`, `requirements.txt`, `README.md`, `DEPLOY.md`, the `mae` folder, `sample_data` folder, `.streamlit` folder)
   and drag it into the GitHub page.
   - Do **not** upload `.venv`, `data` or `uploads` folders if they exist.
   - The `.streamlit` folder may be hidden. Windows: in File Explorer choose **View → Show → Hidden items**.
     Mac: press `Cmd + Shift + .` . (If you skip it, the app still works, just with default colours.)
6. Wait for the files to finish uploading, then click the green **Commit changes** button.
7. Check that `app.py` and the `mae` folder appear in the file list. Done.

---

## Part C — Launch on Streamlit Community Cloud

1. Go to https://share.streamlit.io and click **Continue with GitHub**. Allow access.
2. Click **Create app** (top right) → **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `your-username/attendance-engagement-agent`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** pick a name you like (optional)
4. Click **Advanced settings** → choose **Python 3.11** → Save.
5. Click **Deploy**. The first start takes 3–5 minutes while it installs everything.
6. You get a link like `https://your-name.streamlit.app` — share it with anyone.

### Updating the app later
Go to your GitHub repository → click the file → pencil icon to edit (or **Add file → Upload files** to replace).
Commit the change; the online app updates itself within a minute.

---

## Important things to know

- **Saved data online is temporary.** The free Streamlit service may restart the app (e.g. after inactivity
  or an update), which erases students and attendance stored online. Download your CSV reports regularly
  (Students and Analytics pages), and use the **CSV import** on the Students page to restore your class list.
  For permanent records, run the app on your own computer (Part A).
- **Privacy:** on the online version, uploaded videos are processed on Streamlit's server, not your computer.
  For real classroom footage, prefer running locally.
- The app "sleeps" after a few days unused; open the link and click **"Yes, get this app back up"**.

## Troubleshooting

| Problem | Fix |
|---|---|
| "ModuleNotFoundError" on deploy | Make sure `requirements.txt` and the `mae` folder are in GitHub, at the same level as `app.py`. |
| "File does not exist: app.py" | Main file path must be exactly `app.py` (or `folder/app.py` if you uploaded it inside a folder). |
| `python` not recognised (Windows) | Reinstall Python and tick "Add Python to PATH". |
| App stuck "in the oven" | Click **Manage app** (bottom right) → **⋮** → **Reboot app**. |
