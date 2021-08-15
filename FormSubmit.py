from flask import Flask, render_template, request, redirect, url_for  # For flask implementation
from bson import ObjectId  # For ObjectId to work
from pymongo import MongoClient
import os
import logging

import MangoDb_Sample

app = Flask(__name__)

# allow both GET and POST requests
@app.route('/Login', methods=['GET', 'POST'])
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