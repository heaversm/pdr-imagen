---
title: PDR Vertex
emoji: 📐
colorFrom: indigo
colorTo: pink
sdk: gradio
sdk_version: 4.18.0
app_file: app.py
pinned: false
license: apache-2.0
---

### To recreate this in your own space:

* duplicate this space
* copy the `env-sample` and save as `.env`
* add your OpenAI API Key, and the password you want your users to enter.

### To run locally:

(optional - run in virtual environment)

1	type `virtualenv venv` to create new `venv`
2	type `source venv/bin/activate` to activity `venv`

(required)
3	type pip install -r requirements.txt to install requirements package
4	wait pip install finish
5	type `python app.py`
6	open your browser and type http://127.0.0.1:7860
7	the api docs in http://127.0.0.1:7860/?view=api

### Troubleshooting install

In some environments, such as Mac when you have both python 2 and 3 installed, you may want to run `pip3install -r requirements`, `pip3 install setuptools`, and then `python3 app.py`