import os
import sys

import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv

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

    return response.data[0].url


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