from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017") #host uri
db = client.SaroDB    #Select the database
mydb = db.SaroCollection #Select the collection name

def InsertNewRecord(Name,dob,place):
    print("Inserting New Record")
    insDict ={"name":Name,"dob":dob,"place":place}
    Result=mydb.insert_one(insDict)
    print("Result : ", Result)
    ##mydb.delete_one(insDict)

def ListName():
    nameList = mydb.find({})
    NameList=[]
    for lst in nameList:
        NameList.append(lst)
    return NameList

InsertNewRecord("GV", "Nov","Gobi")