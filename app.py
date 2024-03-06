# file stuff
import os
import sys
import zipfile
import requests
import tempfile
from io import BytesIO
import random
import string

#image generation stuff
from PIL import Image

# gradio / hf / image gen stuff
import gradio as gr
from dotenv import load_dotenv

# stats stuff
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import time

# countdown stuff
from datetime import datetime, timedelta

from google.cloud import aiplatform
import vertexai
# from vertexai.preview.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from vertexai import preview

load_dotenv()


pw_key = os.getenv("PW")

if pw_key == "<YOUR_PW>":
    pw_key = ""

if pw_key == "":
    sys.exit("Please Provide A Password in the Environment Variables")


# Connect to MongoDB
uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(uri, server_api=ServerApi('1'))

mongo_db = mongo_client.pdr
mongo_collection = mongo_db["images"]

image_labels_global = []
image_paths_global = []

#load challenges
challenges = []
with open('challenges.txt', 'r') as file:
    for line in file:
        challenges.append(line.strip())

# pick a random challenge
def get_challenge():
    global challenge
    challenge = random.choice(challenges)
    return challenge

# set initial challenge
challenge = get_challenge()

def update_labels(show_labels):
    updated_gallery = [(path, label if show_labels else "") for path, label in zip(image_paths_global, image_labels_global)]
    return updated_gallery

def generate_images_wrapper(prompts, pw, show_labels):
    global image_paths_global, image_labels_global
    image_paths, image_labels = generate_images(prompts, pw)
    image_paths_global = image_paths

    # store this as a global so we can handle toggle state
    image_labels_global = image_labels
    image_data = [(path, label if show_labels else "") for path, label in zip(image_paths, image_labels)]

    return image_data

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to download image from URL: {url}")

def zip_images(image_paths_and_labels):
    zip_file_path = tempfile.NamedTemporaryFile(delete=False, suffix='.zip').name
    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        for image_url, _ in image_paths_and_labels:
            image_content = download_image(image_url)
            random_filename = ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + ".png"
            # Write the image content to the zip file with the random filename
            zipf.writestr(random_filename, image_content)
    return zip_file_path


def download_all_images():
    global image_paths_global, image_labels_global
    if not image_paths_global:
        raise gr.Error("No images to download.")
    image_paths_and_labels = list(zip(image_paths_global, image_labels_global))
    zip_path = zip_images(image_paths_and_labels)
    image_paths_global = []  # Reset the global variable
    image_labels_global = []  # Reset the global variable
    return zip_path

def generate_images(prompts, pw):
    # Check for a valid password

    if pw != os.getenv("PW"):
        raise gr.Error("Invalid password. Please try again.")

    image_paths = []  # holds urls of images
    image_labels = []  # shows the prompt in the gallery above the image
    users = []  # adds the user to the label

    # Split the prompts string into individual prompts based on semicolon separation
    prompts_list = [prompt for prompt in prompts.split(';') if prompt]

    # model = "claude-3-opus-20240229"

    for i, entry in enumerate(prompts_list):
        entry_parts = entry.split('-', 1)  # Split by the first dash found
        if len(entry_parts) == 2:
            #raise gr.Error("Invalid prompt format. Please ensure it is in 'initials-prompt' format.")
            user_initials, text = entry_parts[0].strip(), entry_parts[1].strip()  # Extract user initials and the prompt
        else:
            text = entry.strip()  # If no initials are provided, use the entire prompt as the text
            user_initials = ""

        users.append(user_initials)  # Append user initials to the list

        prompt_w_challenge = f"{challenge}: {text}"
        print(prompt_w_challenge)

        #how to get model?
        model = ImageGenerationModel.from_pretrained("imagegeneration@002")
        response = model.generate_images(
            prompt=prompt_w_challenge,
            number_of_images=1,
        )

        print(response[0])
        response[0].save(f"image${i}".png)



#custom css
css = """
#gallery-images .caption-label {
    white-space: normal !important;
}
"""


with gr.Blocks(css=css) as demo:

    gr.Markdown("# <center>Prompt de Resistance Claude 3</center>")

    pw = gr.Textbox(label="Password", type="password", placeholder="Enter the password to unlock the service", value="REBEL.pier6moment")

    #instructions
    with gr.Accordion("Instructions & Tips",label="instructions",open=False):
        with gr.Row():
            gr.Markdown("**Instructions**: To use this service, please enter the password. Then generate an image from the prompt field below in response to the challenge, then click the download arrow from the top right of the image to save it.")
            gr.Markdown("**Tips**: Use adjectives (size,color,mood), specify the visual style (realistic,cartoon,8-bit), explain the point of view (from above,first person,wide angle) ")

    #challenge
    challenge_display = gr.Textbox(label="Challenge", value=get_challenge())
    challenge_display.disabled = True
    regenerate_btn = gr.Button("New Challenge")


    #prompts
    with gr.Accordion("Prompts",label="Prompts",open=True):
        text = gr.Textbox(label="What do you want to create?", placeholder="Enter your text and then click on the \"Image Generate\" button")
    with gr.Row():
            btn = gr.Button("Generate Images")

    #output
    with gr.Accordion("Image Outputs",label="Image Outputs",open=True):
        output_images = gr.Gallery(label="Image Outputs", elem_id="gallery-images", show_label=True, columns=[3], rows=[1], object_fit="contain", height="auto", allow_preview=False)
        show_labels = gr.Checkbox(label="Show Labels", value=False)


    with gr.Accordion("Downloads",label="download",open=False):
        download_all_btn = gr.Button("Download All")
        download_link = gr.File(label="Download Zip")

    # generate new challenge
    regenerate_btn.click(fn=get_challenge, inputs=[], outputs=[challenge_display])

    #submissions
    #trigger generation either through hitting enter in the text field, or clicking the button.
    btn.click(fn=generate_images_wrapper, inputs=[text, pw, show_labels ], outputs=output_images, api_name=False)
    text.submit(fn=generate_images_wrapper, inputs=[text, pw, show_labels], outputs=output_images, api_name="generate_image") # Generate an api endpoint in Gradio / HF
    show_labels.change(fn=update_labels, inputs=[show_labels], outputs=[output_images])

    #downloads
    download_all_btn.click(fn=download_all_images, inputs=[], outputs=download_link)

demo.launch(share=False)