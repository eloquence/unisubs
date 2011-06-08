# Universal Subtitles, universalsubtitles.org
# 
# Copyright (C) 2010 Participatory Culture Foundation
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see 
# http://www.gnu.org/licenses/agpl-3.0.html.

from django.db import models
from utils.redis_utils import RedisKey
import datetime

class BasePerDayStatisticModel(models.Model):
    """
    Base Model for saving statistic information in DB
    """
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)
    
    class Meta:
        abstract = True
    
class BasePerDayStatistic(object):
    """
    Base of handler for saving per-day statistic in Redis and migration it to DB.
    For using create subclass and implement *get_key*, *get_object*, *get_query_set*
    methods and *connection*, *prefix*, *model* attributes.
    
    Then create instance and use *update* method with kwargs you need in *get_key*
    method to make unique key for Redis counter.
    For migration use *instance.migrate()* method.
    To get views statistic use *get_views* methods with kwargs to find static
    in database. These kwargs will be passed to *get_query_set* method.
    
    For example, you wish save some view statistic for *Video* object. 
    *BasePerDayStatisticModel* subclass model should have FK to *Video* model.
    Pass *Video* instance to *update* method to update statistic for this video.
    
    Then in *get_key* you get *video* and *date* arguments, where *video* is
    instance you pass to *update* method and *date* is current date. Your *get_key*
    method should return Redis key to update counter. Don't forget about *prefix*
    to prevent collisions.
    Example:
    
        def get_key(self, video, date):
            return '%s:%s:%s' % (self.prefix, video.pk, self.date_format(date))
            
    When *migrate* method is executed, each saved Redis key is checked and
    information is moved to DB. It is saved in *model*. You should implement
    *get_object* method witch should return *model* instance from Redis key 
    to save statistic.
    For example:
    
        def get_object(self, key):
            prefix, pk, date_str = key.split(':')
            date = self.get_date(date_str)
            obj, created = self.model.objects.get_or_create(video_id=pk, date=date)
            return obj
            
    The last method you should implement is *get_query_set*. This method make
    base filtration for QuerySet to get views statistic, because really only you
    know how statistic model is related to some objects. This method get everything
    you pass to *get_views* methods. So if you are using *get_views(video)* this
    can looks like:
    
        def get_query_set(self, video):
            return self.model.objects.filter(video=video)
    
    Really *get_query_set* and *get_key* should get same arguments, because 
    as you update statistic for some objects, for same you wish get this statistic
    in future.
    """
    connection = None   #Redis connection
    prefix = None       #keys' prefix
    model = None        #Model to save info in DB, BasePerDayStatisticModel subclass
    
    def __init__(self):
        if not self.connection:
            raise Exception('Connection undefined')
        
        if not self.prefix:
            raise Exception('Prefix undefined')
        
        if not issubclass(self.model, BasePerDayStatisticModel):
            raise Exception('Model should subclass of BasePerDayStatisticModel')
        
        self.total_key = self._create_total_key()
        self.set_key = self._create_set_key()
    
    def _create_set_key(self):
        return RedisKey('%s:set' % self.prefix, self.connection)
    
    def _create_total_key(self):
        return RedisKey('%s:total' % self.prefix, self.connection)
    
    def date_format(self, date):
        """
        Generate part of Redis key to save *date*
        """
        return '%s-%s-%s' % (date.year, date.month, date.day)
    
    def get_date(self, s):
        """
        Return date from part of Redis key witch was generated by *date_format*
        method
        """
        return datetime.date(*map(int, s.split('-')))       
    
    def get_key(self, date, **kwargs):
        """
        Method should return Redis key for date and arguments passed to update method
        User this format: PREFIX:keys:... 
        or pay attentions that PREFIX:set and PREFIX:total are reserved
        Return None if you wish not save this data
        """
        raise Exception('Not implemented')
    
    def get_object(self, key):
        """
        Method should return instance of self.model for saving statistic in DB
        User self.model. Return None if don't want save this data
        """
        raise Exception('Not implemented')        
    
    def get_query_set(self, **kwargs):
        """
        Should return QuerySet for self.model for get_views method
        """
        raise Exception('Not implemented')
        
    def get_views(self, **kwargs):
        """
        Return views statistic for week and month like: {'month': value, 'week': value, 'year': value}
        Pas
        """
        qs = self.get_query_set(**kwargs)
        today = datetime.date.today()
        week_ago = today - datetime.timedelta(days=7)
        month_ago = today - datetime.timedelta(days=30)
        year_ago = today - datetime.timedelta(days=365)
        
        result = dict(week=0, month=0)
        result['week'] = qs.filter(date__range=(week_ago, today)) \
            .aggregate(s=models.Sum('count'))['s']
        result['month'] = qs.filter(date__range=(month_ago, today)) \
            .aggregate(s=models.Sum('count'))['s']
        result['year'] = qs.filter(date__range=(year_ago, today)) \
            .aggregate(s=models.Sum('count'))['s']
                    
        return result
    
    def migrate(self, verbosity=1):
        """
        Migrate information from Redis to DB
        """
        count = self.set_key.scard()
        
        i = count 
        
        while i:
            if verbosity >= 1:
                print '  >>> migrate key: ', i
                 
            i -= 1
            key = self.set_key.spop()
            if not key:
                break
            
            obj = self.get_object(key)
            if obj:
                obj.count += int(self.connection.getset(key, 0))
                obj.save()
                self.connection.delete(key)
        
        return count
        
    def update(self, **kwargs):
        """
        Update counter for date in Redis
        """
        date = kwargs.get('date', datetime.date.today())
        key = self.get_key(date=date, **kwargs)
        
        if not key:
            return
        
        self.connection.incr(key)
        self.set_key.sadd(key)
        self.total_key.incr()    