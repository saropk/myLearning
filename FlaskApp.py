
from flask import Flask, render_template, request, redirect, url_for  # For flask implementation
from bson import ObjectId  # For ObjectId to work
from pymongo import MongoClient
import os
import logging
import MangoDb_Sample

app = Flask(__name__)

@app.route('/')
def getFunc():
    return render_template('index.html')

@app.route('/AddName')
def addName():
    myFamily=get("https://myfamilytree.free.beeceptor.com")
    Name=request.args.get('adnam')
    dob = request.args.get('addob')
    place=request.args('adplace')
    MangoDb_Sample.InsertNewRecord(Name,dob,place)
    return render_template('ListName.html',arg1=MangoDb_Sample.ListName())

if __name__ == "__main__":
    app.run(debug=True)