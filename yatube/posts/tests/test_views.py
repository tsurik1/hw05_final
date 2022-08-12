import shutil
import tempfile
from random import randint

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..forms import PostForm
from ..models import Group, Post, Follow

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class TaskPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_correct_context_index(self):
        """Правильность контекста главной страницы."""
        response = self.client.get(reverse('posts:index'))
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['page_obj'][0], self.post)

    def test_correct_context_group(self):
        """Правильность контекста списка постов группы."""
        response = self.client.get(reverse(
            'posts:group_list', kwargs={'slug': 'test-slug'}))
        self.assertIn('group', response.context)
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['page_obj'][0].group,
                         self.group)
        self.assertEqual(response.context['page_obj'][0], self.post)

    def test_correct_context_post_detail(self):
        """Тест контекста страницы поста."""
        response = self.client.get(reverse(
            'posts:post_detail', args=(self.post.id,)))
        self.assertIn('post', response.context)
        self.assertEqual(response.context['post'],
                         self.post)

    def test_correct_context_profile(self):
        """Правильность контекста профиля пользователя."""
        response = self.client.get(reverse(
            'posts:profile', kwargs={'username': 'auth'}))
        self.assertIn('author', response.context)
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['author'],
                         self.user)
        self.assertEqual(response.context['page_obj'][0], self.post)

    def test_correct_context_post_edit(self):
        """Контекст страницы создания/редактирования
        поста для авторизованного пользователя."""
        response = self.authorized_client.get(reverse(
            'posts:post_edit', args=(self.post.id,)))
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], PostForm)
        if 'is_edit' in response.context:
            self.assertEqual(response.context['is_edit'], True)


class FollowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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

    def test_an_authorized_user_can_follow(self):
        """Авторизованный пользователь может
        подписываться на других пользователей.
        """
        follows_count = Follow.objects.count()
        test_user = User.objects.create_user(username='pypa')
        self.authorized = Client()
        self.authorized.force_login(test_user)
        self.authorized_client.get(
            reverse('posts:profile_follow', args=(test_user.username,)),
            follow=True)
        self.assertEqual(Follow.objects.count(), follows_count + 1)

    def test_an_authorized_user_can_unfollow(self):
        """Авторизованный пользователь может
        отписываться от других пользователей.
        """
        follows_count = Follow.objects.count()
        test_user = User.objects.create_user(username='pypa')
        self.authorized = Client()
        self.authorized.force_login(test_user)
        self.authorized_client.get(
            reverse('posts:profile_follow', args=(test_user.username,)),
            follow=True)
        self.authorized_client.get(
            reverse('posts:profile_unfollow', args=(test_user.username,)),
        )
        self.assertEqual(Follow.objects.count(), follows_count)

    def test_new_user_record_appears_in_subscribers(self):
        """Новая запись пользователя появляется в 
        ленте тех, кто на него подписан.
        """
        author = User.objects.create_user(username='author')
        authorized_client = Client()
        authorized_client.force_login(author)
        post = Post.objects.create(
            author=self.user,
            text='perfect'
        )
        authorized_client.get(
            reverse('posts:profile_follow', args=(self.user.username,)),
            follow=True)
        response = authorized_client.get(
            reverse('posts:follow_index')
        )
        obj = response.context['page_obj'][0]
        self.assertIn(post.text, obj.text)

        left = User.objects.create_user(username='left')
        authorized_unsubscribers_client = Client()
        authorized_unsubscribers_client.force_login(left)
        response_two = authorized_unsubscribers_client.get(
            reverse('posts:follow_index')
        )
        self.assertNotIn(post.text, response_two)


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


class CacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='test-title',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый постfasdfasdf',
            group=cls.group,
        )

    def test_cache_home_page(self):
        """Тестирование кэша."""
        response = self.client.get(reverse('posts:index'))
        object_index1 = response.content
        last_post = Post.objects.first()
        last_post.delete()
        response = self.client.get(reverse('posts:index'))
        object_index2 = response.content
        self.assertEqual(object_index1, object_index2)
