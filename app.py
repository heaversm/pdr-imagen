import os
import sys

import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# file extension stuff
import requests
import tempfile
from io import BytesIO

load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")
pw_key = os.getenv("PW")

if openai_key == "<YOUR_OPENAI_API_KEY>":
    openai_key = ""

if pw_key == "<YOUR_PW>":
    pw_key = ""

if pw_key == "":
    sys.exit("Please Provide A Password in the Environment Variables")

if openai_key == "":
    sys.exit("Please Provide Your OpenAI API Key")

# Connect to MongoDB
uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(uri, server_api=ServerApi('1'))

mongo_db = mongo_client.pdr
mongo_collection = mongo_db["images"]

# Send a ping to confirm a successful connection
try:
    mongo_client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

def generate_image(text, pw, model):
    # add a conditional to check for a valid password
    if pw != os.getenv("PW"):
        # output an error message to the user in the gradio interface if password is invalid
        raise gr.Error("Invalid password. Please try again.")

    try:
        client = OpenAI(api_key=openai_key)



        response = client.images.generate(
            prompt=text,
            model=model, # dall-e-2 or dall-e-3
            quality="standard", # standard or hd
            size="512x512" if model == "dall-e-2" else "1024x1024", # varies for dalle-2 and dalle-3, see https://openai.com/pricing for resolutions
            n=1, # Number of images to generate
        )
    except Exception as error:
        print(str(error))
        raise gr.Error("An error occurred while generating the image.")

    image_url = response.data[0].url

    try:
        mongo_collection.insert_one({"text": text, "model": model, "image_url": image_url})
    except Exception as e:
        print(e)
        raise gr.Error("An error occurred while saving the prompt to the database.")

    # create a temporary file to store the image with extension
    image_response = requests.get(image_url)
    if image_response.status_code == 200:
        # Use a temporary file to automatically clean up after the file is closed
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(image_response.content)
        temp_file.close()
        # return the file with extension for download
        return temp_file.name
    else:
        raise gr.Error("Failed to download the image.")

    #return image_url


with gr.Blocks() as demo:
    gr.Markdown("# <center> Prompt de Resistance Image Generator</center>")
    gr.Markdown("**Instructions**: To use this service, please enter the password. Then generate an image from the prompt field below, then click the download arrow from the top right of the image to save it.")
    pw = gr.Textbox(label="Password", type="password",
      placeholder="Enter the password to unlock the service")
    text = gr.Textbox(label="What do you want to create?",
      placeholder="Enter your text and then click on the \"Image Generate\" button, "
        "or simply press the Enter key.")

    model = gr.Dropdown(choices=["dall-e-2", "dall-e-3"], label="Model", value="dall-e-3")
    btn = gr.Button("Generate Image")
    output_image = gr.Image(label="Image Output")

    text.submit(fn=generate_image, inputs=[text,pw,model], outputs=output_image, api_name="generate_image")
    btn.click(fn=generate_image, inputs=[text,pw,model], outputs=output_image, api_name=False)

demo.launch(share=True)