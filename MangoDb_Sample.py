from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017") #host uri
db = client.SaroDB    #Select the database
mydb = db.SaroCollection #Select the collection name

def InsertNewRecord():
    print("Inserting New Record")
    insDict ={"name":"GV","dob":"Nov","place":"Gobi"}
    Result=mydb.insert_one(insDict)
    print("Result : ", Result)
    ##mydb.delete_one(insDict)

InsertNewRecord()