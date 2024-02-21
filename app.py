import os
import sys
import zipfile

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

image_paths_global = []

def generate_images_wrapper(prompts, pw, model):
    global image_paths_global
    image_paths = generate_images(prompts, pw, model)
    image_paths_global = image_paths  # Store paths globally
    return image_paths  # You might want to return something else for display

def zip_images(image_paths):
    zip_file_path = tempfile.NamedTemporaryFile(delete=False, suffix='.zip').name
    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        for path in image_paths:
            zipf.write(path, arcname=os.path.basename(path))
            os.remove(path)  # Clean up the temp image file
    return zip_file_path

def download_all_images():
    global image_paths_global
    if not image_paths_global:
        raise gr.Error("No images to download.")
    zip_path = zip_images(image_paths_global)
    image_paths_global = []  # Reset the global variable
    return zip_path

def generate_images(prompts, pw, model):
    # add a conditional to check for a valid password
    if pw != os.getenv("PW"):
        # output an error message to the user in the gradio interface if password is invalid
        raise gr.Error("Invalid password. Please try again.")

    image_paths = []  # Initialize a list to hold paths of generated images
    # Split the prompts string into individual prompts based on comma separation
    prompts_list = prompts.split(';')
    for prompt in prompts_list:
        text = prompt.strip()  # Remove leading/trailing whitespace

        try:
            client = OpenAI(api_key=openai_key)

            response = client.images.generate(
                prompt=text,
                model=model, # dall-e-2 or dall-e-3
                quality="standard", # standard or hd
                size="512x512" if model == "dall-e-2" else "1024x1024", # varies for dalle-2 and dalle-3, see https://openai.com/pricing for resolutions
                n=1, # Number of images to generate
            )


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
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                temp_file.write(image_response.content)
                temp_file.close()
                # return the file with extension for download
                # return temp_file.name
                # append the file with extension to the list of image paths
                print(temp_file.name)
                image_paths.append(temp_file.name)
            else:
                raise gr.Error("Failed to download the image.")
        except Exception as error:
            print(str(error))
            raise gr.Error(f"An error occurred while generating the image for: {prompt}")

    return image_paths


with gr.Blocks() as demo:
    gr.Markdown("# <center> Prompt de Resistance Image Generator</center>")
    gr.Markdown("**Instructions**: To use this service, please enter the password. Then generate an image from the prompt field below, then click the download arrow from the top right of the image to save it.")
    pw = gr.Textbox(label="Password", type="password",
      placeholder="Enter the password to unlock the service")
    text = gr.Textbox(label="What do you want to create?",
      placeholder="Enter your text and then click on the \"Image Generate\" button")

    model = gr.Dropdown(choices=["dall-e-2", "dall-e-3"], label="Model", value="dall-e-3")
    btn = gr.Button("Generate Images")
    # output_image = gr.Image(label="Image Output")
    output_images = gr.Gallery(label="Image Outputs",columns=[3], rows=[1], object_fit="contain", height="auto",allow_preview=False)

    text.submit(fn=generate_images_wrapper, inputs=[text,pw,model], outputs=output_images, api_name="generate_image")
    btn.click(fn=generate_images_wrapper, inputs=[text,pw,model], outputs=output_images, api_name=False)

    download_all_btn = gr.Button("Download All")
    download_link = gr.File(label="Download Zip")
    download_all_btn.click(fn=download_all_images, inputs=[], outputs=download_link)



demo.launch(share=True)