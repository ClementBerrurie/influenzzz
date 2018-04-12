import scrapy
import json
from ..items.InstacrawlItem import InstacrawlItem

class InstagramspiderSpider(scrapy.Spider):
    name = 'instagramspider'
    allowed_domains = ['www.instagram.com']
    start_urls = ['https://www.instagram.com/alexischvt/']
    # start_urls = ['https://www.instagram.com/maneymour/']
    # start_urls = ['http://www.instagram.com/emmanuelmacron/']

    def __init__(self):
        super(InstagramspiderSpider, self).__init__()

        # LOG de connexion pour simuler une connexion, necaissaire pour obtenir les nombre de follows et followers
        self.login  = 'scrapCrawl'
        self.mdp  = 'crawlscrap'

        # Listes contenant les fonctions exécutées dans l'ordre par le 'taskScheduler'
        self.tasks = [
            self.parseProfile,
            self.parseMedias,
            self.parseMediaDetailsOneByOne
        ]

        #Stocke le contenue de la page initial pour les differents parser appellé
        self.initialResponse = ''

        # Les queryHash sont utilisé dans l'élaboration des Urls pour obtenir les likes,commentaires,follows et followers
        self.queryHashLikes = '1cb6ec562846122743b61e492c85999f'
        self.queryHashComment = 'a3b895bdcb9606d5b1ee9926d885b924'
        self.queryHashFollowedBy = '37479f2b8209594dde7facb0d904896a'
        self.queryHashFollow = '58712303d941c6855d4e888c5f0cd22f'
        self.queryHashMedias = '42323d64886122307be10013ad2dcc44'

    # ------------ PARSE --------------
    # Point d'entré de notre programme, il crée l'item et fait appel à notre fonction 'taskScheduler' qui
    # s'occupera de remplir l'item avec ses differentes fonctions.

    #def start_requests(self):
    #    for url in self.start_urls:
    #    yield SplashRequest(url, self.parse, args={'wait': 0.5})

    def parse(self, response):
        self.initialResponse = response
        item = InstacrawlItem()

        #return scrapy.FormRequest.from_response(
        #   response,
        #   formdata={'username': self.login, 'password': self.mdp},
        #   callback=self.after_login
        #)

        return self.taskScheduler(item)

    def after_login(self, response):
        # Verifie si la connexion à échoué
        if "authentication failed" in response.body:
            self.logger.error("Login failed")
            return

        # Création de l'item 'InstacrawlItem' que l'on remplira tous au long de nos fonctions puis sera retourné
        item = InstacrawlItem()

        # Appel de la fonction 'taskScheduler' pour exectuer les premiers parser, on lui passe l'item en paramètre
        return self.taskScheduler(item)

    # ------------ TASK SCHEDULER --------------
    # Fonction qui sera appellé à chaque fin d'utilisation d'un parser
    # A chaque appel d'une fonction celle ci est supprimer des fonctions futures à appeller
    # Lorsqu'il n'y a plus de fonction à appeller, l'item passé en paramètre est retourné pour le pipeline

    def taskScheduler(self, item):
        # Vérifié si il reste toujours des taches à éxécuter :
        # 'self.tasks' renvoi faux si le tableau 'tasks' définie en attribut dans '__init__' est vide
        if self.tasks:
            # Appel de la première fonction présent dans le tableau taskFollowed : 'parseProfile' (Au début)
            # La tache est immédiatement retirer pour que la seconde tache soit exécuter au retour dans la fonction..etc
            return self.tasks.pop(0)(self.initialResponse, item)

        #Certain champs après remplissage sont redondants, on les supprimes donc grace à cette fonction
        item = self.itemCleaner(item)

        # --OPTIONNEL-- Sauvegarde sous format json du profil lu
        self.saveJson(dict(item), 'dataFinal')

        # On retourne l'item rempli avec tous les parser
        # Il sera ensuite sauvegardé en base avec le pipeline
        return item

    # ------------ PARSE PROFILE --------------
    # Initialise le contenue de l'item User avec les informations disponible du profil lu (window.sharedData)
    # Il doit donc être exécuté en premier

    def parseProfile(self, response, item):
        jsonresponse = self.extractSharedData(response)

        # On stock tout le contenue du sharedData dans notre item 'user'
        item['user'] = jsonresponse
        return item

        url_params = '?query_hash=' + self.queryHashFollowedBy + '&variables={"id":"' + str(item['user']['id']) + '","first":' + str(item['user']['edge_followed_by']['count']) + '}'
        request = scrapy.Request('https://www.instagram.com/graphql/query/' + url_params, callback=self.parseFollowedBy)
        request.meta['item'] = item

        #return self.taskScheduler(item)
        #return request

    # Recupère les personnes que suit l'utilisateur
    def parseFollowedBy(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        followedBy = jsonresponse['data']['user']['edge_followed_by']['edges']

        item = response.meta['item']
        item['user']['followed_by']['edges'] = followedBy

        url_params = '?query_hash=' + self.queryHashFollow + '&variables={"id":"' + str(item['user']['id']) + '","first":' + str(item['user']['edge_follow']['count']) + '}'
        request = scrapy.Request('https://www.instagram.com/graphql/query/' + url_params, callback=self.parseFollows)
        request.meta['item'] = item

        return request

    # Recupère les personnes suivit par l'utilisateur
    def parseFollows(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        follows = jsonresponse['data']['user']['edge_follow']['edges']

        item = response.meta['item']
        item['user']['follows']['edges'] = follows

        # On retourne à la fonction de départ pour passer à la prochaine fonction qui est : 'parseMedias'
        return self.taskScheduler(item)

    # ------------ PARSE MEDIAS --------------
    # Lors du chargement de la page toutes les publications (médias) du profil ne sont pas disponible,
    # pour obtenir le reste on fait donc un appel recursif sur cette fonction en incrémentant l'id du premier médias
    # affiché sur la page. Il s'agit du même mécanisme asynchrone lors du défilement la page vers le bas.
    # On peut donc ajouter, à chaque appel recursif, les publications afficher sur la page dans notre item.

    def parseMedias(self, response, item=None):

        medias = []
        # Si on est issue de l'appel recursif, alors l'item n'est pas en parametre mais en metadonnée, il est donc défini
        # par defaut à 'None' comme on peut le voir dans les paramètres de la fonction
        if item is None:
            jsonresponse = json.loads(response.body_as_unicode())
            medias = jsonresponse['data']['user']['edge_owner_to_timeline_media']
            # Récupération de l'item en métadonnée issue de la requète en appel récursif
            item = response.meta['item']
            # Ajout des publication de la page : medias['nodes'] à notre item.
            item['user']['edge_owner_to_timeline_media']['edges'].extend(medias['edges'])
        else :
            jsonresponse = self.extractSharedData(response, True)
            medias = jsonresponse['edge_owner_to_timeline_media']

        # Appel recursif de la fonction parseMedias sur le reste des médias chargé en asynchrone s'il y en a encore
        if medias['page_info']['has_next_page'] is True:
            # Mise ne place du prochain URL à crawler contenant le reste des publications.
            # Pour ce fait on incrémente "max_id" dans l'url, qui correspond à l'id du dernier média lu
            url_params = '?query_hash='+self.queryHashMedias+'&variables={"id":"'+item['user']['id']+'","first":'+ str(item['user']['edge_owner_to_timeline_media']['count'] - 12) +',"after":"'+medias['edges'][-1]['node']['id']+'"}'
            # Création de la requete qui à pour callback cette même fonction
            request = scrapy.Request("https://www.instagram.com/graphql/query/"+url_params, callback=self.parseMedias)
            # On stock notre item en metadonnée dans notre requète avant de l'exécuter.
            request.meta['item'] = item

            # Exécution de la requète
            return request
        else:
            # Dans le dernier appel recursif il n'y a plus de médias à crawler (has_next_page est 'false') alors
            # on retourne à la fonction de départ pour passer à : 'parseMediaDetailsOneByOne'
            return self.taskScheduler(item)

    # ------------ PARSE MEDIA DETAILS --------------

    def parseMediaDetailsOneByOne(self, response, item, index=0):
        mediaNodes = item['user']['edge_owner_to_timeline_media']['edges']

        if len(mediaNodes) == index:
            return self.taskScheduler(item)

        media = mediaNodes[index]['node']

        url_params = "/p/" + media['code'] + "/"
        request = scrapy.Request(response.urljoin(url_params), callback=self.parseMediaDetails)
        request.meta['item'] = item
        request.meta['index'] = index

        return request

    def parseMediaDetails(self, response):
        jsonresponse = self.extractSharedData(response)
        item = response.meta['item']
        index = response.meta['index']

        media = item['user']['edge_owner_to_timeline_media']['edges'][index]['node']

        for key in jsonresponse:
            if key not in media:
                media[key] = jsonresponse[key]

        url_params = '?query_hash=' + self.queryHashLikes + '&variables={"shortcode":"' + str(media['shortcode']) + '","first":' + str(media['likes']['count']) + '}'

        request = scrapy.Request('https://www.instagram.com/graphql/query/' + url_params, callback=self.parseLikes)
        request.meta['item'] = item
        request.meta['index'] = index

        return request

    def parseLikes(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        item = response.meta['item']
        index = response.meta['index']
        media = item['user']['edge_owner_to_timeline_media']['edges'][index]
        likes = jsonresponse['data']['shortcode_media']['edge_liked_by']['edges']
        media['likes']['edges'] = likes

        url_params = '?query_hash=' + self.queryHashComment + '&variables={"shortcode":"' + str(media['shortcode']) + '","first":' + str(media['comments']['count']) + '}'
        request = scrapy.Request('https://www.instagram.com/graphql/query/' + url_params, callback=self.parseComments)
        request.meta['item'] = item
        request.meta['index'] = index

        return request

    def parseComments(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        item = response.meta['item']
        index = response.meta['index']
        media = item['user']['edge_owner_to_timeline_media']['nodes'][index]
        comments = jsonresponse['data']['shortcode_media']['edge_media_to_comment']['edges']
        media['comments']['edges'] = comments

        return self.parseMediaDetailsOneByOne(self.initialResponse, item, index + 1)

    # ------------ TOOLS --------------

    def extractSharedData(self, response, save = False):
        js = response.selector.xpath('//script[contains(., "window._sharedData")]/text()').extract()
        js = js[0].replace("window._sharedData = ", "")
        js = json.loads(js[:-1])

        if save :
            self.saveJson(js)

        if 'ProfilePage' in js['entry_data']:
            return js['entry_data']['ProfilePage'][0]['graphql']['user']

        if 'PostPage' in js['entry_data']:
            return js['entry_data']['PostPage'][0]['graphql']['shortcode_media']

        return false

    def itemCleaner(self, item):
        # del item['user']['saved_media']
        # del item['user']['media_collections']

        # media_saved
        # media_collection
        # code/shortcode (pas sure)
        # edge media to comment deja dans comments
        # edge media preview likes deja dans likes
        # followed by viewer

        return item

    def saveJson(self, data, name='data'):
        try:
            import cPickle as pickle
        except ImportError:  # python 3.x
            import pickle

        with open(name + '.json', 'w') as fp:
            json.dump(data, fp)
