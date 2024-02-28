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
import replicate
from dotenv import load_dotenv

# stats stuff
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import time

# countdown stuff
from datetime import datetime, timedelta


load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

pw_key = os.getenv("PW")

if pw_key == "<YOUR_PW>":
    pw_key = ""

if pw_key == "":
    sys.exit("Please Provide A Password in the Environment Variables")

if REPLICATE_API_TOKEN == "":
    sys.exit("Please Provide Your API Key")

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

def generate_images_wrapper(prompts, pw, model, show_labels):
    global image_paths_global, image_labels_global
    image_paths, image_labels = generate_images(prompts, pw, model)
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

def generate_images(prompts, pw, model):
    # Check for a valid password

    if pw != os.getenv("PW"):
        raise gr.Error("Invalid password. Please try again.")

    image_paths = []  # holds urls of images
    image_labels = []  # shows the prompt in the gallery above the image
    users = []  # adds the user to the label

    # Split the prompts string into individual prompts based on semicolon separation
    prompts_list = [prompt for prompt in prompts.split(';') if prompt]

    for i, entry in enumerate(prompts_list):
        entry_parts = entry.split('-', 1)  # Split by the first dash found
        if len(entry_parts) == 2:
            #raise gr.Error("Invalid prompt format. Please ensure it is in 'initials-prompt' format.")
            user_initials, text = entry_parts[0].strip(), entry_parts[1].strip()  # Extract user initials and the prompt
        else:
            text = entry.strip()  # If no initials are provided, use the entire prompt as the text
            user_initials = ""

        users.append(user_initials)  # Append user initials to the list

        try:
            #openai_client = OpenAI(api_key=openai_key)
            start_time = time.time()

            #make a prompt with the challenge and text
            prompt_w_challenge = f"{challenge}: {text}"

            # stable diffusion
            response = replicate.run(
                "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4",
                input={
                    "width": 768, #must be multiples of 64
                    "height": 768,
                    "prompt": prompt_w_challenge,
                    "scheduler": "K_EULER", #controlling the steps of the diffusion process to balance between image quality, generation speed, and resource consumption - DDIM, K_EULER, DPMSolverMultistep, K_EULER_ANCESTRAL, PNDM, KLMS
                    "num_outputs": 1, #images to generate
                    "guidance_scale": 7.5, #0-20, higher the number, more it sticks to the prompt
                    "num_inference_steps": 50 #1-500 - higher the better, generally
                }
            )
            print(response)

            end_time = time.time()
            gen_time = end_time - start_time  # total generation time

            #image_url = response.data[0].url
            image_url = response[0]

            # conditionally render the user to the label with the prompt
            image_label = f"{i}: {text}" if user_initials == "" else f"{i}: {user_initials}-{text}, "

            try:
                # Save the prompt, model, image URL, generation time and creation timestamp to the database
                mongo_collection.insert_one({"user": user_initials, "text": text, "model": model, "image_url": image_url, "gen_time": gen_time, "timestamp": time.time()})
            except Exception as e:
                print(e)
                raise gr.Error("An error occurred while saving the prompt to the database.")

            # Append the image URL and label to their respective lists
            image_paths.append(image_url)
            image_labels.append(image_label)

        except Exception as e:
            print(e)
            raise gr.Error(f"An error occurred while generating the image for: {entry}")

    return image_paths, image_labels  # Return both image paths and labels


#timer stuff
timer_cancelled_global = False # when true, timer does not tick down

def countdown(seconds):
  """
  This function takes the number of seconds as input and returns a string displaying the remaining time.
  """
  target_time = datetime.now() + timedelta(seconds=int(seconds))
  while target_time > datetime.now():
    remaining_time = target_time - datetime.now()
    remaining_seconds = int(remaining_time.total_seconds())
    yield f"{remaining_seconds:02d}"
    # Check if the countdown was cancelled
    if timer_cancelled_global:
      break

def stop_countdown():
  """
  This function stops the countdown.
  """
  global timer_cancelled_global
  timer_cancelled_global = True

def reset_countdown(slider):
  """
  This function resets the countdown.
  """
  global timer_cancelled_global
  timer_cancelled_global = False
  return 60


#custom css
css = """
#gallery-images .caption-label {
    white-space: normal !important;
}
"""


with gr.Blocks(css=css) as demo:

    gr.Markdown("# <center>Prompt de Resistance Stable Diffusion</center>")

    pw = gr.Textbox(label="Password", type="password", placeholder="Enter the password to unlock the service")

    #instructions
    with gr.Accordion("Instructions & Tips",label="instructions",open=False):
        with gr.Row():
            gr.Markdown("**Instructions**: To use this service, please enter the password. Then generate an image from the prompt field below in response to the challenge, then click the download arrow from the top right of the image to save it.")
            gr.Markdown("**Tips**: Use adjectives (size,color,mood), specify the visual style (realistic,cartoon,8-bit), explain the point of view (from above,first person,wide angle) ")

    #challenge
    challenge_display = gr.Textbox(label="Challenge", value=get_challenge())
    challenge_display.disabled = True
    regenerate_btn = gr.Button("New Challenge")


    #countdown
    with gr.Accordion("Countdown",label="Countdown",open=False):
        with gr.Row():
            with gr.Column(scale=3):
                slider = gr.Slider(minimum=1, maximum=120, value=60,label="Countdown",info="Select duration in seconds")
            with gr.Column(scale=1):
                countdown_button = gr.Button("Start")
                stop_countdown_button = gr.Button("Stop")
                reset_countdown_button = gr.Button("Reset")


    #prompts
    with gr.Accordion("Prompts",label="Prompts",open=True):
        with gr.Row():
            with gr.Column(scale=3):
                text = gr.Textbox(label="What do you want to create?", placeholder="Enter your text and then click on the \"Image Generate\" button")
            with gr.Column(scale=1):
                model = gr.Dropdown(choices=["stable-diffusion"], label="Model", value="stable-diffusion")
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

    #countdown
    countdown_button.click(fn=countdown, inputs=[slider], outputs=[slider])
    stop_countdown_button.click(fn=stop_countdown)
    reset_countdown_button.click(fn=reset_countdown,inputs=[slider],outputs=[slider])

    #submissions
    #trigger generation either through hitting enter in the text field, or clicking the button.
    btn.click(fn=generate_images_wrapper, inputs=[text, pw, model, show_labels], outputs=output_images, api_name=False)
    text.submit(fn=generate_images_wrapper, inputs=[text, pw, model, show_labels], outputs=output_images, api_name="generate_image") # Generate an api endpoint in Gradio / HF
    show_labels.change(fn=update_labels, inputs=[show_labels], outputs=[output_images])

    #downloads
    download_all_btn.click(fn=download_all_images, inputs=[], outputs=download_link)

demo.launch(share=False)