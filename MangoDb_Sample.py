from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017") #host uri
db = client.SaroDB    #Select the database
mydb = db.SaroCollection #Select the collection name
LoginCol=db.Login

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

def Validate(Userid, PassWord):
    checkError=LoginCol.find({"User_ID":Userid, "Password":PassWord}).count()
    print ("Error Status : ", checkError)
    print("Error Status : ", type(checkError))
    if checkError==0:
        return -1
    else:
        return 0

##InsertNewRecord("GV", "Nov","Gobi")