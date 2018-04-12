# -*- coding: utf-8 -*-
import scrapy
import json
import re
from ..items.youtubecrawlItem import YoutubecrawlItem

class youtubeSpider(scrapy.Spider):
    name = 'youtubespider'
    allowed_domains = ["www.youtube.com", "www.googleapis.com"]
    API_KEY = "AIzaSyBM3qGvuEPE37774qdfseWvOzRhIbUt4Uc"
    PART = "snippet,brandingSettings,topicDetails,contentOwnerDetails,contentDetails,statistics"
    start_urls = ['https://www.googleapis.com/youtube/v3/channels?key='+API_KEY+'&part='+PART+'&forUsername=williamVEVO']

    def __init__(self):
        super(youtubeSpider, self).__init__()
        self.ChannelId = ''
        self.playlists = []

    def parse(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        item = YoutubecrawlItem()
        item['chanel'] = jsonresponse['items'][0]

        self.ChannelId = item['chanel']['id']

        url_params = '?key=' + self.API_KEY + '&part=snippet,contentDetails&channelId=' + self.ChannelId
        request = scrapy.Request('https://www.googleapis.com/youtube/v3/subscriptions' + url_params,callback=self.parseSubscriptions)
        request.meta['item'] = item

        return request

    def parseSubscriptions(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        item = response.meta['item']
        item['chanel']['Subscriptions'] = jsonresponse['items']

        url_params = '?key=' + self.API_KEY + '&part=snippet,contentDetails&channelId=' + self.ChannelId
        request = scrapy.Request('https://www.googleapis.com/youtube/v3/channelSections' + url_params,callback=self.parseChannelSection)
        request.meta['item'] = item

        return request

    def parseChannelSection(self, response):
        jsonresponse = json.loads(response.body_as_unicode())
        item = response.meta['item']
        item['chanel']['ChannelSections'] = jsonresponse['items']

        for channelSection in item['chanel']['ChannelSections']:
            if channelSection['snippet']['type'] == 'singlePlaylist':
                self.playlists.append(channelSection['contentDetails']['playlists'][0])

        return self.parsePlaylists(response, item)

    def parsePlaylists(self, response, item = None):

        if item is None :
            item = response.meta['item']

            if response.status != 404:
                jsonresponse = json.loads(response.body_as_unicode())
                oldPlaylistId = re.search('playlistId=(.*)', response.request.url).group(1)
                item['chanel'][oldPlaylistId] = jsonresponse['items']

        if self.playlists:
            playlistId = self.playlists.pop(0)
            url_params = '?key=' + self.API_KEY + '&maxResults=50&part=snippet,contentDetails&playlistId=' + playlistId
            request = scrapy.Request('https://www.googleapis.com/youtube/v3/playlistItems' + url_params, callback=self.parsePlaylists)
            request.meta['item'] = item

            return request

        return item

