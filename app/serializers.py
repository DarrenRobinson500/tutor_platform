from rest_framework import serializers
from .models import *

class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = "__all__"

class SkillSerializer(serializers.ModelSerializer):
    children_count = serializers.IntegerField(source="children.count", read_only=True)
    template_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Skill
        fields = [
            "id",
            "parent",
            "code",
            "description",
            "grade_level",
            "order_index",
            "children_count",
            "template_count",
        ]

class SkillDetailSerializer(serializers.ModelSerializer):
    children = SkillSerializer(many=True, read_only=True)
    children_count = serializers.IntegerField(source="children.count", read_only=True)
    template_count = serializers.SerializerMethodField()

    def get_template_count(self, obj):
        return obj.template_count()

    class Meta:
        model = Skill
        fields = [
            "id",
            "parent",
            "code",
            "description",
            "grade_level",
            "order_index",
            "children",
            "children_count",
            "template_count",
        ]

