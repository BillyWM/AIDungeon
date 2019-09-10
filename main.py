import datetime
from flask import g
from flask import session
import os
import googleapiclient.discovery
from utils import *
from google.cloud import storage
from google import cloud
import json
from flask import Flask, render_template, request, abort
from flask import Response
import requests
import pdb
import sys
from generator import StoryGenerator
import gpt2.src.encoder as encoder


# App Info
phrases = [" You attack", " You use", " You tell", " You go"]
prompts = ["You enter a dungeon with your trusty sword and shield. You are searching for the evil necromancer who killed your family. You've heard that he resides at the bottom of the dungeon, guarded by legions of the undead. You enter the first door and see"]
continuing_prompts = ["You are in a dungeon with your sword and shield. You are on a quest to defeat the necromancer. This dungeon is full of zombie and skeletons."]
app = Flask(__name__)
app.secret_key = '#d\xe0\xd1\xfb\xee\xa4\xbb\xd0\xf0/e)\xb5g\xdd<`\xc7\xa5\xb0-\xb8d0S'

# Encoder Info
encoder_path='gpt2/models/117M'
enc = encoder.get_encoder(encoder_path)

# Model/Cache Info
project = "ai-adventure"
model = "generator_v1"
version = "version2"
os.environ['GOOGLE_APPLICATION_CREDENTIALS']="./AI-Adventure-2bb65e3a4e2f.json"
storage_client = storage.Client()
bucket = storage_client.get_bucket("dungeon-cache")

# Local generator functionality
RUN_LOCAL = False
local_generator = None
def get_local_generator():
    if "gen" not in g:
        if "sess" not in g:
            g.sess = tf.Session()
        g.gen = StoryGenerator(g.sess)

    return g.gen


@app.teardown_appcontext
def teardown_sess(_):
    sess = g.pop("sess", None)

    if sess is not None:
        sess.close()

def predict(context_tokens):
    service = googleapiclient.discovery.build('ml', 'v1')
    name = 'projects/{}/models/{}'.format(project, model)
    instance = context_tokens

    if version is not None:
        name += '/versions/{}'.format(version)

    response = service.projects(). predict(
        name=name,
        body={'instances': [{'context': instance}]}
    ).execute()

    if 'error' in response:
        raise RuntimeError(response['error'])

    return response['predictions']
    
    
def generate(prompt):

    while(True):
        context_tokens = enc.encode(prompt)
        try:
            pred = predict(context_tokens)
            pred = pred[0]["output"][len(context_tokens):]
            output = enc.decode(pred)
            return output
        except:
            print("generate request failed, trying again")
            continue


def generate_story_block(prompt, local=False):

    if local:
        generator = get_local_generator()
        block = generator.generate(prompt)
    else:
        block = generate(prompt)

    block = cut_trailing_sentence(block)
    block = story_replace(block)
    return block


def generate_action_result(prompt, phrase, local=False):

    if local:
        generator = get_local_generator()
        action = phrase + generator.generate(prompt + phrase)
    else:
        action = phrase + generate(prompt + phrase)

    action_result = cut_trailing_sentence(action)
    action_result = story_replace(action_result)
    action = first_sentence(action)

    return action, action_result
    
@app.route('/')
def root():
    seed = -1
    data = {'seed': seed}
    return render_template('index.html', data=data)

@app.route('/<seed>')
def rootseed(seed):
    if seed == "":
        seed = -1
    else:
        seed = int(seed)
    data = {'seed': seed}
    session["seed"] = seed
    return render_template('index.html', data=data)

@app.route('/index.html')
def index():
    data = {'seed': -1}
    return render_template('index.html', data=data)

@app.route('/about.html')
def about():
    return render_template('about.html')


def cache_file(seed, prompt_num, choices, response, tag):
    return
    # blob_file_name = "prompt" + str(prompt_num) + "/seed" + str(seed) + "/" + tag
    # for action in choices:
    #     blob_file_name = blob_file_name + str(action)
    # blob = bucket.blob(blob_file_name)
    #
    # blob.upload_from_string(response)
    #
    # print("File ", blob_file_name, " cached")


def retrieve_from_cache(seed, prompt_num, choices, tag):
    return None
    # blob_file_name = "prompt" + str(prompt_num) + "/seed" + str(seed) + "/" + tag
    #
    # for action in choices:
    #     blob_file_name = blob_file_name + str(action)
    #
    # blob = bucket.blob(blob_file_name)
    #
    # if blob.exists(storage_client):
    #     result = blob.download_as_string().decode("utf-8")
    #     print(blob_file_name, " found in cache")
    # else:
    #     result = None
    #     print(blob_file_name, " not found in cache")
    #
    # return result


@app.route('/generate', methods=['POST'])
def story_request():
    print("****Generating Story****")
    seed = request.form["seed"]
    prompt_num = int(request.form["prompt_num"])
    gen_actions = request.form["actions"]

    print("Session Seed is ", session["seed"])

    if int(seed) < 0 or int(seed) > 100:
        #print("Invalid seed: " + seed)
        abort(404)

    if gen_actions == "true":

        #prompt = request.form["prompt"]
        choices = json.loads(request.form["choices"])
        #print("Getting response for seed ", seed, " prompt_num ", prompt_num, " and choices ", choices)
        
        action_results = retrieve_from_cache(seed, prompt_num, choices, "choices")

        if action_results is not None:
            response = action_results
        else:
            last_action_result = request.form["last_action_result"]
            prompt = continuing_prompts[prompt_num] + last_action_result
            #print("\n\nAction prompt is \n ", prompt)
            action_results = [generate_action_result(prompt, phrase, local=RUN_LOCAL) for phrase in phrases]
            response = json.dumps(action_results)
            cache_file(seed, prompt_num, choices, response, "choices")
    else:

        #print("Getting response for seed ", seed, " prompt_num ", prompt_num)
        result = retrieve_from_cache(seed, prompt_num, [], "story")

        if result is not None:
            response = result
        else:
            prompt = prompts[prompt_num]
            response = generate_story_block(prompt, local=RUN_LOCAL)
            cache_file(seed, prompt_num, [], response, "story")

    #print("\nGenerated response is: \n", response)
    #print("")

    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)