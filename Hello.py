print ('Hello World!!!!')
print ('This is my Frist Python Prgram')

def MyProcedure():
  print('testing procedure')

MyProcedure()

a = {"name" : "Saro","age":44, }
print (a["name"],  a["age"])

a.update(state='TN')

print(a)
#country=input("Enter Country")
#a.keys = "country"
#a.values= country
#print (country)

a,b,c = 1,2,{'name':"Saravanakumar P",'place':'Sathy'}
print(c)
print(isinstance((a,b), (int, int)))
print (type(c))
mylist = []
mylist.insert(0,"testing")
mylist.append(2)
for x in mylist:
  print (type(x))
  print (x)

out = a+b+7.77
print(out)
print(5%3)
print ("testinmultiply"*10)
od = [1,3,5]
ev = [2,4,6]
tot = od+ev
print(tot)
TotSort = tot.sort()
print (tot)
print (TotSort)
print ([1,2,3]*4)
print ('My nmae is %s' % c["name"])
print (c["name"].index("a"))
print (c["name"][13:8:-2].upper())
print (c["name"].startswith("ara"))
print (c["name"])
cc = {'name':"Saravanakumar P",'place':'Sathy'}
print (cc)
print (c)
print (cc == c)
print (cc is c)