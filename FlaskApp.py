
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
    #return render_template('ListName.html',arg1=MangoDb_Sample.ListName())

@app.route('/ListName')
def lstName():
    return render_template('ListName.html', arg1=MangoDb_Sample.ListName())

@app.route('/NameSave1')
def NameSave1(dictInput):
    Name = dictInput.Name
    dob = dictInput.DOB
    City = dictInput.City
    Place = dictInput.Place
    MangoDb_Sample.InsertNewRecord(Name, dob, Place)

@app.route('/NameSave/<Name1>',methods=['POST'])
def NameSave(Name1):
    MangoDb_Sample.InsertNewRecord(Name1, 'test', 'CBE')
    return "success"

@app.route('/Login',methods=['POST','GET'])
def Login():
    print("Request Method:",request.method)
    print ("Inside Login Function - Start")
    Uid=request.form.get('UserID')
    Pwd=request.form.get('User_Password')
    print ("Inside Login Function - Before Validation:",Uid,Pwd)
    ##MangoDb_Sample.InsertNewRecord(Uid,Pwd,Validation)
    return render_template('ListName.html', arg1=MangoDb_Sample.ListName())
    if (Validation==0):
        return render_template('ListName.html', arg1=MangoDb_Sample.ListName())
    else:
        return render_template('ListName.html', arg1=MangoDb_Sample.ListName())


# allow both GET and POST requests
@app.route('/Login1', methods=['GET', 'POST'])
def form_example():
    if request.method=='POST':
        UiD=request.form.get('UserID')
        PwD=request.form.get('PWD')
        print ("User ID & Pwd : ",UiD,PwD)
        ret_Login = MangoDb_Sample.Validate(UiD,PwD)
        if ret_Login==0:
            return render_template('ListName.html', arg1=MangoDb_Sample.ListName())
    return '''
              <form method="POST">
                  <div><label>User ID: <input type="text" name="UserID"></label></div>
                  <div><label>Password: <input type="password" name="PWD"></label></div>
                  <input type="submit" value="Submit">
              </form>'''


if __name__ == "__main__":
    app.run(debug=True)