import json,requests,sys,os
from multiprocessing import Manager,Process,Value


class CityList:
    def __init__(self,path):
        self.data = {}
        with open(path) as f:
            for i in f:
                d = json.loads(i)
                self.data[d["_id"]]=d
        self.keys = self.data.keys()

    def __getitem__(self,index):
        if(index in self.keys): return self.data[index]
        return self.data[self.keys[index]]

    def __iter__(self):
        return self.data.__iter__()

class WeatherCrawler:
    def __init__(self,url,APPID,n):
        self.url=url
        self.APPID = APPID
        self.results = Manager().list()
        self.n=n

    def update_visited(self,l):
        self.visited = l

    def request(self,ID):
        ret = requests.request("GET",self.url+("?id=%s&APPID=%s" % (ID,self.APPID)))
        return  ret

    def execute(self,cityIDList,PM,verbose=False):
        for cityID in cityIDList:
            if cityID in self.visited:continue
            try:
                result = self.request(cityID)
                self.visited.append(cityID)
                with PM.count.get_lock():
                    PM.count.value+=1
                if(result.status_code<400):
                    self.results.append(json.loads(result.content))
                    if verbose:
                        print "\r%d/%d -- "%(PM.count.value,self.n),
                        print "city:%s requested sucessfully."%cityID,

                else:
                    if verbose:print "city:%s failed to access"%cityID
                    return
            except requests.ConnectionError, e:
                print "\n",e
            sys.stdout.flush()

class ResultManager:
    def __init__(self,path):
        self.path=path
        self.res=Manager().list()

    def dump(self):
        with open(self.path,"wb") as f:
            f.write(json.dumps(self.res))
        print "\n%d records has been stored" % len(self.res)

    def loadPrev(self):
        if(not os.path.exists(self.path)):
            self.res=[]
            print "No file \"%s\" found, create a new file"%self.path
            self.dump()
        with open(self.path) as f:
            self.res = json.loads(f.next())
        print "%d previous records are found." % len(self.res)

class ProcessingManager:
    def __init__(self,numThread,resMgr,crawlerClass,cities,url,APPIDs):
        self.resMgr=resMgr
        self.crawlerClass=crawlerClass
        self.url = url
        self.APPIDs = APPIDs
        self.nthread = numThread
        self.crawlers = []
        self.jobs = []
        self.cities = cities

    def __enter__(self):
        self.resMgr.loadPrev()
        visited = [d["id"] for d in self.resMgr.res]
        self.count = Value('i',len(visited))
        unvisited = list(set(self.cities)-set(visited))
        global left
        left = len(unvisited)
        print "%d left."%left
        avg = left/self.nthread
        remain = left%self.nthread
        for i in xrange(min([left,self.nthread])):
            self.crawlers.append(self.crawlerClass(self.url,self.APPIDs[i%len(self.APPIDs)],len(self.cities)))
            self.crawlers[i].update_visited(visited)
            self.jobs.append(unvisited[i*avg + min([i,remain]):(i+1)*avg + min([i+1,remain])])
        return self

    def __exit__(self,*argv):
        for crawler in self.crawlers:
            self.resMgr.res+=crawler.results
        self.resMgr.dump()



if __name__=="__main__":
    APPIDs=[i.strip() for i in open("./APPIDs.txt")]
    url_main = "http://api.openweathermap.org/data/2.5/weather"
    cities_path = "./city.list.us.json"
    data_path = "./data/crawledData"

    resMgr = ResultManager(data_path)
    cityListTotal = CityList(cities_path)
    left = -1

    while True:
        with ProcessingManager(50,resMgr,WeatherCrawler,cityListTotal.keys,url_main,APPIDs) as PM:
            q = []
            for i in xrange(min([left,PM.nthread])):
                crawler = PM.crawlers[i]
                p = Process(target = crawler.execute, args = (PM.jobs[i],PM,True))
                p.start()
                q.append(p)
            for p in q:
                p.join()
        if left==0:
            break
    print "ALL SET!"
