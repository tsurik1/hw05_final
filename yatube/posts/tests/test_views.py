import tempfile

from random import randint

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache

from ..forms import PostForm

from ..models import Group, Post

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class TaskPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.small_gif,
            content_type='image/gif'
        )
        cls.group = Group.objects.create(
            title='test-title',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый постfasdfasdf',
            group=cls.group,
            image=cls.uploaded
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_correct_context_index(self):
        """Тест проверки контекста для индексной страницы."""
        response = self.client.get(reverse('posts:index'))
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['page_obj'][0], self.post)

    def test_correct_context_group(self):
        """Тест контекста страницы группы."""
        response = self.client.get(reverse(
            'posts:group_list', kwargs={'slug': 'test-slug'}))
        self.assertIn('group', response.context)
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['page_obj'][0].group,
                         self.group)
        self.assertEqual(response.context['page_obj'][0], self.post)

    def test_correct_context_profile(self):
        """Тест контекста страницы профиля."""
        response = self.client.get(reverse(
            'posts:profile', kwargs={'username': 'auth'}))
        self.assertIn('author', response.context)
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['author'],
                         self.user)
        self.assertEqual(response.context['page_obj'][0], self.post)

    def test_correct_context_post_detail(self):
        """Тест контекста страницы поста."""
        response = self.client.get(reverse(
            'posts:post_detail', args=(self.post.id,)))
        self.assertIn('post', response.context)
        self.assertEqual(response.context['post'],
                         self.post)

    def test_correct_context_post_edit(self):
        """Тест контекста страниц создания/редактирования поста."""
        response = self.authorized_client.get(reverse(
            'posts:post_edit', args=(self.post.id,)))
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], PostForm)
        if 'is_edit' in response.context:
            self.assertEqual(response.context['is_edit'], True)

    def test_post_creation_check(self):
        """Проверка при создании поста."""
        test_post = Post.objects.create(
            author=self.user,
            text='Тестовый пост',
            group=self.group,
            image=self.uploaded
        )
        response = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(response.context['page_obj'][0].text,
                         test_post.text)

        response = self.authorized_client.get(reverse(
            'posts:group_list', kwargs={'slug': 'test-slug'}))
        self.assertEqual(response.context['page_obj'][0].text,
                         test_post.text)

        response = self.authorized_client.get(reverse(
            'posts:profile', kwargs={'username': 'auth'}))
        self.assertEqual(response.context['page_obj'][0].text,
                         test_post.text)

    def test_cache_home_page(self):
        """Тестирование кэша."""
        response = self.client.get(reverse('posts:index'))
        object_index1 = response.content
        last_post = Post.objects.first()
        last_post.delete()
        response = self.client.get(reverse('posts:index'))
        object_index2 = response.content
        self.assertEqual(object_index1, object_index2)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='test-title',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.posts_count = randint(
            settings.NUMBER_OF_POSTED + 1, settings.NUMBER_OF_POSTED * 2)

        Post.objects.bulk_create([Post(
            author=cls.user,
            text='Тестовый постfasdfasdf',
            group=cls.group)
            for _ in range(cls.posts_count)])

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_page_contains_ten_records(self):
        """тестирование паджинатора 1-2 стр"""
        pages = {
            '?page=1': settings.NUMBER_OF_POSTED,
            '?page=2': self.posts_count - settings.NUMBER_OF_POSTED
        }
        for address, counts in pages.items():
            with self.subTest(address=address):
                response = self.client.get(reverse('posts:index') + address)
        self.assertEqual(len(response.context.get(
            'page_obj').object_list), counts)
