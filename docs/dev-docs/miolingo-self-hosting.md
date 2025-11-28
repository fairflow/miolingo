<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# espeak is a standard Python library; we built a local version to enable sound, a common problem on a mac.  But we don't need to use that.  We do need to play recordings, and can use .wav if needed.  Can you give me a workflow for checking this out in detail please?  We do have ssh enabled and have been able to use it.

You should be able to run this on Emerald using Krystal’s Python App + your existing SSH, treating audio as simple .wav file serving and playback in the browser.[^1][^2]

## Overview of the workflow

- Use cPanel “Setup Python App” to create a Python environment and entry point for your Streamlit app.[^2][^3]
- Via SSH / the app console, install your app and its dependencies into that virtualenv (including `streamlit` and any audio libraries).[^1][^2]
- Arrange your .wav files so they are accessible to the app (e.g. in the repo or a static folder), and use Streamlit’s media functions to play them in the browser.[^4][^5]


## Step 1 – Create the Python app in cPanel

- In Krystal cPanel, go to “Setup Python App” (or “Python Apps”), click “Create Application”, choose your Python version (matching your local dev if possible), and note the “Application root” path and the internal port it assigns.[^3][^2]
- The wizard will create a virtual environment under your account and give you an “Open” or “Open Console” button plus an example `passenger_wsgi.py`/entry file. You will not use WSGI for Streamlit, but you want the virtualenv and app root.[^2][^1]


## Step 2 – Deploy your code and requirements

- Push your code to a Git repo or zip it and upload/extract into the “Application root” directory defined in the Python App (e.g. `/home/USER/miolingo_streamlit`).[^1][^2]
- Place `requirements.txt` there (with `streamlit`, `espeak` if purely Python, and anything you need for audio and Portuguese processing). Then use “Open Console” for that Python app or SSH into the server and run the app’s activation command that Krystal provides, followed by `pip install -r requirements.txt` inside that virtualenv.[^3][^2][^1]


## Step 3 – Adjust the Streamlit command and config

- In your app root, add a small launcher script, e.g. `start_streamlit.sh`, that activates the virtualenv and runs `streamlit run your_main.py --server.port=XXXX --server.address=0.0.0.0`, where `XXXX` is the port used by your Python App (or another allowed port; you may need to experiment a little within Krystal’s guidance).[^5][^6]
- Ensure Streamlit is configured for a sub‑path or domain if needed (e.g. via `.streamlit/config.toml` with `server.baseUrlPath` and `browser.serverAddress` set appropriately) so that when Krystal proxies HTTP traffic to that port, Streamlit’s assets load correctly.[^7][^8]


## Step 4 – Handling .wav recordings

- Put your audio files under a folder in the app root (e.g. `audio/word_001.wav`). Streamlit can read them and play them directly in the browser using `st.audio(open("audio/word_001.wav","rb").read(), format="audio/wav")`, which does not require system‑level sound on the server.[^4][^5]
- Confirm locally that all sound paths and relative directories work, then push the same structure to the server so paths match; Krystal’s shared hosting is fine with serving these as static files from disk via the Python process.[^9][^2]


## Step 5 – Make it reachable from the web

- Krystal’s Python App tool lets you map a domain or subdomain to your Python application, typically using Passenger behind Apache; you may need to configure it so HTTP requests hit your running Streamlit process (on the internal port) rather than expecting a WSGI callable.[^2][^1]
- If the built‑in mapping is too tied to WSGI, an alternative is to run Streamlit on an internal port and then use cPanel’s app routing or a small rewrite/proxy rule (if exposed in your plan) so that `https://yourdomain/miolingo` forwards to that port. Krystal’s “developer hosting” docs encourage this pattern for custom frameworks.[^9][^1]


## Step 6 – Debug and iterate over SSH

- Use SSH (with the Krystal‑documented command) to attach to the app’s directory, run the launch script manually, and watch Streamlit’s logs while you access the app in a browser; this is the fastest way to chase import or path issues.[^10][^11]
- If you hit a wall with the Python App/Passenger integration, the next step Krystal themselves recommend for more complex custom apps is moving to a VPS/Katapult server, where you can run Streamlit as a normal long‑running service behind Nginx.[^12][^9]

If you paste your current `requirements.txt` and main `streamlit` entry file name, it is possible to turn this into a concrete `pip install` command list and a sample `start_streamlit.sh` tailored to your setup.
<span style="display:none">[^13]</span>

<div align="center">⁂</div>

[^1]: https://masterdaweb.com/en/blog/how-to-host-your-python-application-on-cpanel

[^2]: https://help.krystal.io/python/python-apps

[^3]: https://help.krystal.io/python

[^4]: https://streamlit.io

[^5]: https://github.com/streamlit/streamlit

[^6]: https://discuss.streamlit.io/t/deployment-of-streamlit-app-on-a-remote-server/8468

[^7]: https://github.com/streamlit/streamlit/issues/1716

[^8]: https://docs.streamlit.io/knowledge-base/deploy/deploy-streamlit-domain-port-80

[^9]: https://krystal.io/developer-hosting

[^10]: https://help.krystal.io/cpanel-advanced-topics/how-do-i-get-ssh-secure-shell-access

[^11]: https://help.krystal.io/cpanel-advanced-topics/shell-access-to-your-server-using-ssh-mac-os-terminal

[^12]: https://help.krystal.io/getting-started/what-is-vps-hosting-and-is-it-right-for-me

[^13]: https://miolingo3.streamlit.app/

