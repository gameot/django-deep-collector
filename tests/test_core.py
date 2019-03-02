
from django.test import TestCase

from .factories import (BaseModelFactory, ManyToManyToBaseModelFactory,
                        ForeignKeyToBaseModelFactory, ClassLevel3Factory,
                        ManyToManyToBaseModelWithRelatedNameFactory,
                        SubClassOfBaseModelFactory)
from deep_collector.utils import DeepCollector, RelatedObjectsCollector
from .models import (ForeignKeyToBaseModel, InvalidFKRootModel, InvalidFKNonRootModel, BaseModel, GFKModel,
                     BaseToGFKModel)


class TestDirectRelations(TestCase):

    def test_get_foreign_key_object(self):
        obj = BaseModelFactory.create()

        collector = DeepCollector()
        collector.collect(obj)
        self.assertIn(obj.fkey, collector.get_collected_objects())

    def test_get_one_to_one_object(self):
        obj = BaseModelFactory.create()

        collector = DeepCollector()
        collector.collect(obj)
        self.assertIn(obj.o2o, collector.get_collected_objects())

    def test_get_many_to_many_object(self):
        obj = BaseModelFactory.create()
        m2m_model = ManyToManyToBaseModelFactory.create(base_models=[obj])

        collector = DeepCollector()
        collector.collect(m2m_model)
        self.assertIn(obj, collector.get_collected_objects())

    def test_one_to_one_object_inherited(self):
        obj = SubClassOfBaseModelFactory.create()

        collector = DeepCollector()
        collector.collect(obj)
        self.assertIn(obj.o2o, collector.get_collected_objects())


class TestReverseRelations(TestCase):

    def test_get_reverse_foreign_key_object(self):
        fkey_model = ForeignKeyToBaseModelFactory.create()

        collector = DeepCollector()
        collector.collect(fkey_model.fkeyto)
        self.assertIn(fkey_model, collector.get_collected_objects())

    def test_get_reverse_many_to_many_object(self):
        obj = BaseModelFactory.create()
        m2m_model = ManyToManyToBaseModelFactory.create(base_models=[obj])

        collector = DeepCollector()
        collector.collect(obj)
        self.assertIn(m2m_model, collector.get_collected_objects())


class TestNestedObjects(TestCase):

    def test_recursive_foreign_keys(self):
        level3 = ClassLevel3Factory.create()
        level2 = level3.fkey
        level1 = level2.fkey

        collector = DeepCollector()

        # Double reverse field collection
        collector.collect(level1)
        collected_objs = collector.get_collected_objects()
        self.assertIn(level1, collected_objs)
        self.assertIn(level2, collected_objs)
        self.assertIn(level3, collected_objs)

        # Middle class collection (1 direct field and 1 reverse field)
        collector.collect(level2)
        collected_objs = collector.get_collected_objects()
        self.assertIn(level1, collected_objs)
        self.assertIn(level2, collected_objs)
        self.assertIn(level3, collected_objs)

        # Double direct field collection
        collector.collect(level3)
        collected_objs = collector.get_collected_objects()
        self.assertIn(level1, collected_objs)
        self.assertIn(level2, collected_objs)
        self.assertIn(level3, collected_objs)


class TestCollectorParameters(TestCase):

    def test_model_is_excluded_when_defined_in_models_exclude_list(self):
        obj = BaseModelFactory.create()

        collector = DeepCollector()
        collector.EXCLUDE_MODELS = ['tests.o2odummymodel']
        collector.collect(obj)

        self.assertNotIn(obj.o2o, collector.get_collected_objects())

    def test_direct_field_is_excluded_when_defined_in_direct_field_exclude_list(self):
        obj = BaseModelFactory.create()

        collector = DeepCollector()
        collector.EXCLUDE_DIRECT_FIELDS = {
            'tests.basemodel': ['fkey']
        }
        collector.collect(obj)

        self.assertNotIn(obj.fkey, collector.get_collected_objects())

    def test_related_field_is_excluded_when_defined_in_related_field_exclude_list(self):
        obj = BaseModelFactory.create()
        m2m_model = ManyToManyToBaseModelFactory.create(base_models=[obj])

        collector = DeepCollector()
        collector.EXCLUDE_RELATED_FIELDS = {
            'tests.basemodel': ['manytomanytobasemodel_set']
        }
        collector.collect(obj)

        self.assertNotIn(m2m_model, collector.get_collected_objects())

    def test_related_field__with_related_name_is_excluded_when_defined_in_related_field_exclude_list(self):
        obj = BaseModelFactory.create()
        m2m_model = ManyToManyToBaseModelWithRelatedNameFactory.create(base_models=[obj])

        collector = DeepCollector()
        collector.EXCLUDE_RELATED_FIELDS = {
            'tests.basemodel': ['custom_related_m2m_name']
        }
        collector.collect(obj)

        self.assertNotIn(m2m_model, collector.get_collected_objects())

    def test_parameter_to_avoid_collect_if_too_many_related_objects(self):
        obj = BaseModelFactory.create()
        ForeignKeyToBaseModelFactory.create_batch(fkeyto=obj, size=3)

        collector = DeepCollector()
        collector.MAXIMUM_RELATED_INSTANCES = 3
        collector.collect(obj)
        collected_objects = collector.get_collected_objects()

        self.assertEquals(len([x for x in collected_objects if isinstance(x, ForeignKeyToBaseModel)]), 3)

        # If we have more related objects than expected, we are not collecting them, to avoid a too big collection
        collector.MAXIMUM_RELATED_INSTANCES = 2
        collector.collect(obj)
        collected_objects = collector.get_collected_objects()
        self.assertEquals(len([x for x in collected_objects if isinstance(x, ForeignKeyToBaseModel)]), 0)

        self.assertDictEqual({
            'parent_instance': u'tests.basemodel.%s' % obj.pk,
            'field_name': u'foreignkeytobasemodel_set',
            'related_model': u'tests.foreignkeytobasemodel',
            'count': 3,
            'max_count': 2,
        }, collector.get_report()['excluded_fields'][0])

    def test_parameter_to_avoid_collect_on_specific_model_if_too_many_related_objects(self):
        obj = BaseModelFactory.create()
        fkey1 = ForeignKeyToBaseModelFactory(fkeyto=obj)
        fkey2 = ForeignKeyToBaseModelFactory(fkeyto=obj)
        fkey3 = ForeignKeyToBaseModelFactory(fkeyto=obj)

        collector = DeepCollector()
        # If model is specified in MAXIMUM_RELATED_INSTANCES_PER_MODEL, we don't take into account
        # MAXIMUM_RELATED_INSTANCES parameter
        collector.MAXIMUM_RELATED_INSTANCES = 1
        collector.MAXIMUM_RELATED_INSTANCES_PER_MODEL = {'tests.foreignkeytobasemodel': 3}
        collector.collect(obj)
        collected_objects = collector.get_collected_objects()

        self.assertEquals(len([x for x in collected_objects if isinstance(x, ForeignKeyToBaseModel)]), 3)
        self.assertEquals(len(collector.get_report()['excluded_fields']), 0)

        # If we have more related objects than expected, we are not collecting them, to avoid a too big collection
        collector = DeepCollector()
        collector.MAXIMUM_RELATED_INSTANCES = 1
        collector.MAXIMUM_RELATED_INSTANCES_PER_MODEL = {'tests.foreignkeytobasemodel': 2}
        collector.collect(obj)
        collected_objects = collector.get_collected_objects()

        self.assertEquals(len([x for x in collected_objects if isinstance(x, ForeignKeyToBaseModel)]), 0)

        self.assertEquals(len(collector.get_report()['excluded_fields']), 1)
        self.assertDictEqual({
            'parent_instance': u'tests.basemodel.%s' % obj.pk,
            'field_name': u'foreignkeytobasemodel_set',
            'related_model': u'tests.foreignkeytobasemodel',
            'count': 3,
            'max_count': 2,
        }, collector.get_report()['excluded_fields'][0])

    def test_parameter_to_avoid_collect_if_too_many_related_objects_through_many_to_many_field(self):
        obj1 = BaseModelFactory.create()
        obj2 = BaseModelFactory.create()
        obj3 = BaseModelFactory.create()
        root_obj = ManyToManyToBaseModelFactory.create(base_models=[obj1, obj2, obj3])

        collector = DeepCollector()
        collector.MAXIMUM_RELATED_INSTANCES = 3
        collector.collect(root_obj)
        collected_objects = collector.get_collected_objects()

        self.assertEquals(len([x for x in collected_objects if isinstance(x, BaseModel)]), 3)
        self.assertEquals(len(collector.get_report()['excluded_fields']), 0)

        # If we have more related objects than expected, we are not collecting them, to avoid a too big collection
        collector.MAXIMUM_RELATED_INSTANCES = 2
        collector.collect(root_obj)
        collected_objects = collector.get_collected_objects()
        self.assertEquals(len([x for x in collected_objects if isinstance(x, BaseModel)]), 0)

        self.assertEquals(len(collector.get_report()['excluded_fields']), 1)
        self.assertDictEqual({
            'parent_instance': u'tests.manytomanytobasemodel.%s' % root_obj.pk,
            'field_name': u'm2m',
            'related_model': u'tests.basemodel',
            'count': 3,
            'max_count': 2,
        }, collector.get_report()['excluded_fields'][0])

    def test_parameter_to_avoid_collect_on_specific_model_if_too_many_related_objects_through_many_to_many_field(self):
        obj1 = BaseModelFactory.create()
        obj2 = BaseModelFactory.create()
        obj3 = BaseModelFactory.create()
        root_obj = ManyToManyToBaseModelFactory.create(base_models=[obj1, obj2, obj3])

        collector = DeepCollector()
        collector.MAXIMUM_RELATED_INSTANCES = 1
        collector.MAXIMUM_RELATED_INSTANCES_PER_MODEL = {'tests.basemodel': 3}
        collector.collect(root_obj)
        collected_objects = collector.get_collected_objects()

        self.assertEquals(len([x for x in collected_objects if isinstance(x, BaseModel)]), 3)
        self.assertEquals(len(collector.get_report()['excluded_fields']), 0)

        # If we have more related objects than expected, we are not collecting them, to avoid a too big collection
        collector.MAXIMUM_RELATED_INSTANCES = 1
        collector.MAXIMUM_RELATED_INSTANCES_PER_MODEL = {'tests.basemodel': 2}
        collector.collect(root_obj)
        collected_objects = collector.get_collected_objects()
        self.assertEquals(len([x for x in collected_objects if isinstance(x, BaseModel)]), 0)

        self.assertEquals(len(collector.get_report()['excluded_fields']), 1)
        self.assertDictEqual({
            'parent_instance': u'tests.manytomanytobasemodel.%s' % root_obj.pk,
            'field_name': u'm2m',
            'related_model': u'tests.basemodel',
            'count': 3,
            'max_count': 2,
        }, collector.get_report()['excluded_fields'][0])


class TestPostCollect(TestCase):
    @staticmethod
    def _generate_invalid_id(model):
        instance = model.objects.create()
        invalid_id = instance.id
        instance.delete()
        return invalid_id

    def test_invalid_foreign_key_doesnt_cause_matching_query_does_not_exist_exception(self):
        root = InvalidFKRootModel.objects.create()
        non_root = InvalidFKNonRootModel.objects.create()

        root.invalid_fk_id = self._generate_invalid_id(InvalidFKNonRootModel)
        root.valid_fk = non_root
        root.save()

        non_root.invalid_fk_id = self._generate_invalid_id(InvalidFKRootModel)
        non_root.valid_fk = root
        non_root.save()

        # when post_collect() is executed on the InvalidFKRootModel instance
        # this invalid foreign key shouldn't cause an error like:
        # "DoesNotExist: InvalidFKRootModel matching query does not exist."
        # OR
        # "DoesNotExist: InvalidFKNonRootModel matching query does not exist."

        collector = DeepCollector()
        collector.collect(root)

        self.assertIn(root, collector.get_collected_objects())
        self.assertIn(non_root, collector.get_collected_objects())


class TestGFKRelation(TestCase):

    def test_get_gfk_key_object(self):
        obj = BaseModelFactory.create()
        gfkmodel = GFKModel.objects.create(content_object=obj)

        collector = DeepCollector()
        collector.collect(gfkmodel)
        self.assertIn(obj, collector.get_collected_objects())

    def test_doesnt_automatically_get_reverse_gfk_key_object(self):
        obj = BaseModelFactory.create()
        gfkmodel = GFKModel.objects.create(content_object=obj)

        collector = DeepCollector()
        collector.collect(obj)
        self.assertNotIn(gfkmodel, collector.get_collected_objects())

    def test_get_reverse_gfk_key_object_if_generic_relation_is_explicitly_defined(self):
        obj = BaseToGFKModel.objects.create()
        gfkmodel = GFKModel.objects.create(content_object=obj)

        collector = DeepCollector()
        collector.collect(obj)
        self.assertIn(gfkmodel, collector.get_collected_objects())

    def test_reverse_objects_collection_limit(self):
        obj = BaseToGFKModel.objects.create()
        gfkmodel = GFKModel.objects.create(content_object=obj)
        gfkmodel2 = GFKModel.objects.create(content_object=obj)

        collector = DeepCollector()
        collector.MAXIMUM_RELATED_INSTANCES_PER_MODEL = {'tests.gfkmodel': 1}
        collector.collect(obj)
        self.assertNotIn(gfkmodel, collector.get_collected_objects())
        self.assertNotIn(gfkmodel2, collector.get_collected_objects())


class TestBackwardCompatibility(TestCase):

    def test_get_foreign_key_object(self):
        obj = BaseModelFactory.create()

        collector = RelatedObjectsCollector()
        collector.collect(obj)
        self.assertIn(obj.fkey, collector.get_collected_objects())
