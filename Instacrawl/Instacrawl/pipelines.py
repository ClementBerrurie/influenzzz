import pymongo

class MongoPipeline(object):

    collection_name = 'instagramSpider'                                    #Nom de la collection utilisée pour la sauvegarde

    def __init__(self, mongo_uri, mongo_db):                           #Initialisation des attributs de la classe pour la connexion
        self.mongo_uri = "localhost:27017"                             #Url de la base
        self.mongo_db = "influenzzz"                                   #Nom de la base

    @classmethod
    def from_crawler(cls, crawler):                                    #Définition de la fonction d'instanciation de la connexion à la base
        return cls(
            mongo_uri=crawler.settings.get('MONGO_URI'),               #Association de l'attribut au paramètre du crawler concernant l'url de la base
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'items')   #Association de l'attribut au paramètre du crawler concernant le nom de la base
        )

    def open_spider(self, spider):                                     #Fonction appellée au yield de l'item dans la spider
        self.client = pymongo.MongoClient(self.mongo_uri)              #Création du client MongoDB
        self.db = self.client[self.mongo_db]                           #Création de la base au partir du client MongoDB

    def close_spider(self, spider):                                    #Fonction appellée a la fermeture
        self.client.close()                                            #Fermeture du client MongoDb

    def process_item(self, item, spider):                              #Fonction appellé pour le traitement des données
        self.db[self.collection_name].insert_one(dict(item))           #Enregsitrement en base de l'item sous la forme d'un dictionnaire
        return item