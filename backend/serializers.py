from rest_framework import serializers
from .models import *

class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = "__all__"
        read_only_fields = ['id']

class SkillSerializer(serializers.ModelSerializer):
    children_count = serializers.IntegerField(source="children.count", read_only=True)
    template_count = serializers.IntegerField(read_only=True)
    parent_id = serializers.IntegerField(source="parent.id", allow_null=True)

    class Meta:
        model = Skill
        fields = ["id", "parent_id", "code", "description", "grades", "order_index", "children_count", "template_count", "validated_count", "unvalidated_count",]

# class SkillDetailSerializer(serializers.ModelSerializer):
#     children = SkillSerializer(many=True, read_only=True)
#     children_count = serializers.IntegerField(source="children.count", read_only=True)
#     template_count = serializers.SerializerMethodField()
#
#     def get_template_count(self, obj):
#         return obj.template_count()
#
#     class Meta:
#         model = Skill
#         fields = ["id", "parent", "code", "description", "grades", "order_index", "children", "children_count", "template_count"]

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role"]

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ["id", "user", "year_level", "area_of_study"]
        read_only_fields = ["id", "user"]

        depth = 1

class TutorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorProfile
        fields = ["id", "tutor", "logo", "color_scheme", "welcome_message", "default_session_minutes", "buffer_minutes", "token", "created_at"]
        depth = 1  # includes user details

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = "__all__"
        read_only_fields = ["id", "author", "created_at"]

