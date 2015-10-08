# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.lru_cache import lru_cache

try:
    from lxml import etree
except ImportError:
    raise CommandError('Missing dependency. Please, install lxml>=2.3.3')

from teryt_tree.models import Category, JednostkaAdministracyjna


@lru_cache()
def get_genre(name, level):
    obj, _ = Category.objects.get_or_create(name=name, defaults={'level': level})
    return obj


class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = ('Creates a data in database base on Teryt.xml file.')
    PARENT_REDUCE = {2: 0,
                     4: 2,
                     7: 4}
    LEVEL_REDUCE = {2: 1,
                    4: 2,
                    7: 3}

    def add_arguments(self, parser):
        parser.add_argument('filename', type=str)

    @classmethod
    def to_object(cls, row, commit=True):
        data = {x.get('name').lower(): x.text for x in row}
        obj = JednostkaAdministracyjna()
        obj.active = True
        obj.id = "".join(data.get(x, '') or '' for x in ('woj', 'pow', 'gmi', 'rodz'))
        index = len(obj.pk)
        if len(obj.id) > 2:
            obj.parent = JednostkaAdministracyjna.objects.get(pk=obj.id[:cls.PARENT_REDUCE[index]])
        obj.name = data['nazwa'].title()
        obj.updated_on = data['stan_na']
        obj.category = get_genre(data['nazdod'], cls.LEVEL_REDUCE[index])
        return obj

    def handle(self, *args, **options):
        root = etree.parse(options['filename'])
        self.stdout.write(("Importing started. "
                           "This may take a few seconds. Please wait a moment.\n"))
        row_count = 0
        with transaction.atomic():
            with JednostkaAdministracyjna.objects.delay_mptt_updates():
                for row in root.iter('row'):
                    obj = Command.to_object(row)
                    obj.save()
                    row_count += 1
        self.stdout.write("%s rows imported.\n" % row_count)
