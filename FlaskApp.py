
from flask import Flask, render_template, request, redirect, url_for  # For flask implementation
from bson import ObjectId  # For ObjectId to work
from pymongo import MongoClient
import os
import logging
import orderInsert

app = Flask(__name__)

@app.route('/')
def getFunc():

if __name__ == "__main__":
    app.run(debug=True)