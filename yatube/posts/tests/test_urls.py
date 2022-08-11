from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.core.cache import cache

from ..models import Group, Post

User = get_user_model()


class StaticURLTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='test-title',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый постfasdfasdf',
        )

    def setUp(self):
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_urls_status_code_guest(self):
        """Тестирование публичных адресов."""
        templates_url_names = (
            reverse('posts:index'),
            reverse('posts:group_list', args=(self.group.slug,)),
            reverse('posts:profile', args=(self.user,)),
            reverse('posts:post_detail', args=(self.post.id,)),
        )
        for address in templates_url_names:
            with self.subTest(address=address):
                response = self.client.get(address)
                self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_urls_status_code_authorized(self):
        """Тестирование адресов, доступных автору поста."""
        self.authorized_client.force_login(StaticURLTests.user)
        templates_url_names = (
            reverse('posts:post_edit', args=(self.post.id,)),
            reverse('posts:create_post'),
        )
        for address in templates_url_names:
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_unexisting(self):
        """Тестирование несуществующей страницы."""
        response = self.client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_url_names = {
            'posts/index.html': reverse('posts:index'),
            'posts/group_list.html': reverse(
                'posts:group_list', args=(self.group.slug,)),
            'posts/profile.html': reverse(
                'posts:profile', args=(self.user,)),
            'posts/post_detail.html': reverse(
                'posts:post_detail', args=(self.post.id,)),
        }
        for template, address in templates_url_names.items():
            with self.subTest(address=address):
                response = self.client.get(address)
                self.assertTemplateUsed(response, template)

    def test_urls_404(self):
        """Страница 404 отдает соответсвующий шаблон."""
        response = self.client.get('/unexisting_page/')
        self.assertTemplateUsed(response, 'core/404.html')

    def test_private_pages_for_author(self):
        """Тестирование доступности шаблонов приватных страниц автора."""
        self.authorized_client.force_login(StaticURLTests.user)
        templates_url_names = (
            reverse('posts:create_post'),
            reverse('posts:post_edit', args=(self.post.id,)),
        )
        for address in templates_url_names:
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, 'posts/create_post.html')

    def test_private_address_redirect(self):
        """Тестирование перенаправления не автора на логин."""
        lgn = reverse('users:login')
        templates_url_names = (
            reverse('posts:create_post'),
            reverse('posts:post_edit', args=(self.post.id,)),
        )
        for address in templates_url_names:
            with self.subTest(address=address):
                response = self.client.get(address)
        self.assertRedirects(response, f'{lgn}?next={address}')

    def test_not_the_author_leads_to_the_post_view_page(self):
        """Тестирование перенаправления не автора на страницу поста."""
        response = self.authorized_client.post(
            reverse('posts:post_edit', args=(self.post.id,)))
        self.assertRedirects(response, reverse(
            'posts:post_detail', args=(self.post.id,)))
