import facebook as fb
import sqlalchemy as sql
from sqlalchemy import Column, Integer, String,ForeignKey,Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref,sessionmaker,session,scoped_session

import json
from dateutil import parser
import datetime
import os
from PySide.QtGui import *
from PySide.QtCore import *

Base = declarative_base()
at="109906609107292|_3rxWMZ_v1UoRroMVkbGKs_ammI"
g=fb.GraphAPI("109906609107292|_3rxWMZ_v1UoRroMVkbGKs_ammI")


def getDictValue(data,multikey):
    keys=multikey.split('.')                
    value=data
    for key in keys:
        if type(value) is dict:
            value=value.get(key,"")
        else:
            return ""    
    return value                    
    
class Database(object):
    
    def __init__(self):
        self.connected=False
        self.filename=""
        
    def connect(self,filename):
        try:   
            if self.connected:
                self.disconnect()
 
            self.engine = create_engine('sqlite:///%s'%filename, convert_unicode=True)
            self.session = scoped_session(sessionmaker(autocommit=False,autoflush=False,bind=self.engine))
            Base.query = self.session.query_property()
            Base.metadata.create_all(bind=self.engine)
            self.filename=filename
            self.connected=True
        except Exception as e:
            self.filename=""
            self.connected=False
            err=QErrorMessage()
            err.showMessage(str(e))
                
    def disconnect(self):
        if self.connected:
            self.session.close()
            
        self.filename=""    
        self.connected=False
        
    def createconnect(self,filename):    
        self.disconnect()
        if os.path.isfile(filename):
            os.remove(filename)
        self.connect(filename)     
                    
    def commit(self):
        if self.connected:
            try:
                self.session.commit()
            except Exception as e:
                err=QErrorMessage()
                err.showMessage(str(e))
        else:
            err=QErrorMessage()
            err.showMessage("No database connection")

    def rollback(self):
        if self.connected:
            try:
                self.session.rollback()
            except Exception as e:
                err=QErrorMessage()
                err.showMessage(str(e))
        else:
            err=QErrorMessage()
            err.showMessage("No database connection")            
            


            
class Node(Base):
        __tablename__='Nodes'

        facebookid=Column(String)
        querystatus=Column(String)
        querytype=Column(String)
        querytime=Column(String)
        response_raw=Column("response",Text)                                        
        id=Column(Integer,primary_key=True)
        parent_id = Column(Integer, ForeignKey('Nodes.id'))
        children = relationship("Node",backref=backref('parent', remote_side=[id]))
        level=Column(Integer)                             
        childcount=Column(Integer)

        def __init__(self,facebookid,parent_id=None):            
            self.facebookid=facebookid
            self.parent_id=parent_id
            self.level=0
            self.childcount=0
            self.querystatus='new'
            
        @property
        def response(self):
            if (self.response_raw == None): 
                return {}
            else:
                return  json.loads(self.response_raw)
    
        @response.setter
        def response(self, response_raw):
            self.response_raw = json.dumps(response_raw)               
            
        def getResponseValue(self,key):
            return getDictValue(self.response,key)
            
        
                      

class TreeItem(object):
    def __init__(self, parent=None,id=None,data=None):
        self.id = id
        self.parentItem = parent        
        self.data = data
        self.childItems = []
        self.loaded=False                
        self._childcountallloaded=False
        self._childcountall=0

    def appendChild(self, item,persistent=False):
        item.parentItem=self
        self.childItems.append(item)
        if persistent:
            self._childcountall += 1

    def child(self, row):
        return self.childItems[row]
    
    def clear(self):
        self.childItems=[]
        self.loaded=False
        self._childcountallloaded=False
        
    def remove(self,persistent=False):
        self.parentItem.removeChild(self,persistent)            
        

    def removeChild(self,child,persistent=False):
        if child in self.childItems:            
            self.childItems.remove(child)
            if persistent:
                self._childcountall -= 1        
        
    def childCount(self):
        return len(self.childItems)
    
    def childCountAll(self):       
        if not self._childcountallloaded:                                     
            self._childcountall=Node.query.filter(Node.parent_id == self.id).count()
            self._childcountallloaded=True            
        return self._childcountall     
            
    def parent(self):
        return self.parentItem

    def level(self):
        if self.data == None:
            return 0
        else:
            return self.data['level']

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

    

class TreeModel(QAbstractItemModel):
    
    def __init__(self, mainWindow=None,database=None):
        super(TreeModel, self).__init__()
        self.mainWindow=mainWindow
        self.customcolumns=[]
        self.rootItem = TreeItem()
        self.database=database

    def reset(self):        
        self.rootItem.clear()
        super(TreeModel, self).reset()        
                   
    def setCustomColumns(self,newcolumns=[]):
        self.customcolumns=newcolumns
        self.layoutChanged.emit()    
                            

    def deleteNode(self,index):
        if (not self.database.connected) or (not index.isValid()) or (index.column() <> 0):
            return False                                               

        self.beginRemoveRows(index.parent(),index.row(),index.row())
        item=index.internalPointer()                   
        Node.query.filter(Node.id == item.id).delete()                            
        self.database.session.commit()                         
        item.remove(True)       
        self.endRemoveRows()

            
    def addNodes(self,facebookids):
        try:       
            if not self.database.connected:
                return False
                
            self.beginInsertRows(QModelIndex(),self.rootItem.childCount(),self.rootItem.childCount()+len(facebookids)-1)
               
            for facebookid in facebookids: 
                new=Node(facebookid)
                self.database.session.add(new)
                self.database.session.flush()
                itemdata=self.getItemData(new)     
                self.rootItem.appendChild(TreeItem(self.rootItem,new.id,itemdata),True)
                #self.createIndex(row, 0, index)
                         
            self.database.session.commit()                        
            self.endInsertRows()

                                    
        except Exception as e:
            err=QErrorMessage(self.mainWindow)
            err.showMessage(str(e))        

    def queryData(self,index,relation=None,options={}):
        if not index.isValid():
            return False
        
        if (relation!=None) and (relation!=''):
            self.queryRelations(index,relation,options)
        else:   
            treenode=index.internalPointer()
            dbnode=Node.query.get(treenode.id)             
            
            try:
                url=dbnode.facebookid+'&metadata=1'
                response = g.get_object(url)                                                
                dbnode.response = response
            except Exception as e:
                dbnode.querystatus=str(e)
            else:
                dbnode.querystatus="fetched"
            
            dbnode.querytime=str(datetime.datetime.now())
            dbnode.querytype=""
            self.database.session.commit()
            treenode.data=self.getItemData(dbnode)
            
            self.layoutChanged.emit()
                                  
        
    def queryRelations(self,index,relation,options={}):
        if not index.isValid():
            return False
        
        parentitem=index.internalPointer()        
        dbnode=Node.query.get(parentitem.id) 
        try:
            #liker=g.get_object(str('/fql&q=select user_id from like where post_id="%s" and user_id=%s limit 500'%(self.id,self.site_id)))            
            #nodes=g.get_object(str(self.id+'/feed&limit='+str(n)+'&since='+since+'&until='+until))['data']
            default={'limit':100,'metadata':1}                
            default.update(options)
            
            optionstring=''
            for option in default:
                optionstring+='&'+option+'='+str(default[option])
            url=str(dbnode.facebookid)+'/'+relation+optionstring
            
            response=g.get_object(url)
            nodes=response['data']
            
            rowcount=self.rowCount(index)
            self.beginInsertRows(index,rowcount,rowcount+len(nodes)-1)
            
            
            for n in nodes:
                #if n.get("id") not in [x.id for x in self.children]]
                new=Node(n.get("id"),dbnode.id)
                new.response=n
                new.level=dbnode.level+1
                new.querystatus="fetched"
                new.querytime=str(datetime.datetime.now())
                new.querytype=relation
                dbnode.children.append(new)
                self.database.session.flush()
                
                itemdata=self.getItemData(new)     
                parentitem.appendChild(TreeItem(parentitem,new.id,itemdata),True)

                
            dbnode.childcount += len(nodes)    
            self.database.session.commit()
            
            self.endInsertRows()
        except Exception as e:
            err=QErrorMessage()
            err.showMessage(str(e))
                                
    def columnCount(self, parent):
        return 4+len(self.customcolumns)    

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()
                                             

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            captions=['Facebook ID','Query Status','Query Time','Query Type']+self.customcolumns                
            return captions[section] if section < len(captions) else ""

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()
        
          
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

            
    def data(self, index, role):
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        item = index.internalPointer()
        
        if index.column()==0:
            return item.data['facebookid']
        elif index.column()==1:
            return item.data['querystatus']      
        elif index.column()==2:
            return item.data['querytime']      
        elif index.column()==3:
            return item.data['querytype']      
        else:            
            return getDictValue(item.data['response'],self.customcolumns[index.column()-4])
            

    def hasChildren(self, index):
        if not self.database.connected:
            return False
                
        if not index.isValid():
            item = self.rootItem
        else:
            item = index.internalPointer()                                
        
        return item.childCountAll() > 0               
            
        
            

    def getItemData(self,item):
        itemdata={}
        itemdata['level']=item.level
        itemdata['facebookid']=item.facebookid        
        itemdata['querystatus']=item.querystatus
        itemdata['querytime']=item.querytime
        itemdata['querytype']=item.querytype
        itemdata['response']=item.response     
        return itemdata   
        
    def canFetchMore(self, index):                           
        if not self.database.connected:
            return False
        
        if not index.isValid():
            item = self.rootItem
        else:
            item = index.internalPointer()    
                            
        return item.childCountAll() > item.childCount()
        
    def fetchMore(self, index):
        if not index.isValid():
            parent = self.rootItem
        else:
            parent = index.internalPointer()                       
        
        if parent.childCountAll() == parent.childCount():
            return False
                
        row=parent.childCount()        
        items = Node.query.filter(Node.parent_id == parent.id).all()

        
        self.beginInsertRows(index,row,row+len(items)-1)

        for item in items:
            itemdata=self.getItemData(item)
            new=TreeItem(parent,item.id,itemdata)
            new._childcountall=item.childcount
            new._childcountallloaded=True                                                               
            parent.appendChild(new)
            self.createIndex(row, 0, index)
            row += 1
                                        
        self.endInsertRows()
        parent.loaded=parent.childCountAll()==parent.childCount()


                    
    
