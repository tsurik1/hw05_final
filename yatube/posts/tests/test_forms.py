import shutil
import tempfile
from http import HTTPStatus

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Group, Post, User

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTest(TestCase):
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
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый постfasdfasdf',
            group=cls.group,
            image=cls.uploaded
        )
        cls.comment = Comment.objects.create(
            text='Тестовый комментарий',
            post=cls.post,
            author=cls.user
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_count_post(self):
        """Создание поста при отправке валидной
        формы авторизованным пользователем."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый пост',
            'group': self.group.pk,
            'image': self.uploaded,
        }
        responce = self.authorized_client.post(reverse('posts:create_post'),
                                               data=form_data, follow=True)

        last_post = Post.objects.first()

        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertEqual(last_post.text, form_data['text'])
        self.assertEqual(last_post.author, self.user)
        self.assertEqual(last_post.group, PostFormTest.group)
        self.assertRedirects(responce, reverse('posts:profile', kwargs={
                             'username': PostFormTest.user.username}))

    def test_post_change(self):
        """Редактирование поста при отправке валидной формы автором поста."""
        new_group = Group.objects.create(
            title='test group',
            slug='slugg',
        )
        test_post = Post.objects.create(
            author=self.user,
            text='test text',
            group=new_group,
        )
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Текст из формы',
            'group': new_group.id,
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', args=(test_post.id,)), data=form_data)
        self.assertEqual(Post.objects.count(), posts_count)
        test_post.refresh_from_db()
        self.assertEqual(test_post.text, form_data['text'])
        self.assertEqual(test_post.author, self.user)
        self.assertEqual(test_post.group, new_group)
        self.assertRedirects(response, reverse(
            'posts:post_detail', args=(test_post.id,)))

    def test_redirect_client_to_login(self):
        """Неавторизованный пользователь не может создать пост,
        и его перенаправляет на страницу авторизации."""
        posts_count = Post.objects.count()
        response = self.guest_client.post(
            reverse('posts:create_post'), follow=True
        )
        lgn = reverse('users:login')
        crt = reverse('posts:create_post')
        self.assertRedirects(response, f'{lgn}?next={crt}')
        self.assertEqual(Post.objects.count(), posts_count)

    def test_redirect(self):
        """Авторизованный пользователь не может редактировать 
        чужой пост и перенаправляется на страницу поста."""
        new_group = Group.objects.create(
            title='test group',
            slug='slugg',
        )
        test_post = Post.objects.create(
            author=self.user,
            text='test text',
            group=new_group,
        )

        test_group = Group.objects.create(
            title='test',
            slug='sluggi',
        )
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Текст из формы',
            'group': test_group.id,
        }
        user = User.objects.create_user(username='test-auth')
        self.client.force_login(user)
        response = self.client.post(reverse(
            'posts:post_edit', args=(test_post.id,)), data=form_data
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail', args=(test_post.id,)))
        self.assertNotEqual(test_post.text, form_data['text'])
        self.assertNotEqual(test_post.group, form_data['group'])
        self.assertEqual(Post.objects.count(), posts_count)

    def test_an_authorized_user_can_create_a_comment(self):
        """Авторизованный пользователь может создать комментарий, 
        происходит редирект на страницу поста."""
        comments_count = Comment.objects.count()
        form_data = {
            'text': 'Тестовый текст из формы теста',
        }
        response = self.authorized_client.post(
            reverse(
                'posts:add_comment',
                args=(self.post.id,)
            ),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, f'/posts/{self.post.id}/')
        self.assertTrue(
            Comment.objects.filter(
                text='Тестовый текст из формы теста'
            ).exists()
        )
        self.assertEqual(Comment.objects.count(), comments_count + 1)

    def test_only_authorized_user_can_comment(self):
        """Неавторизованный пользователь не может создать комментарий,
        происходит редирект на страницу авторизации."""
        form_data = {
            'text': 'test comment',
        }
        response = self.client.post(reverse(
            'posts:add_comment', args=(self.post.id,)), data=form_data
        )
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        lgn = reverse('users:login')
        crt = reverse('posts:add_comment', args=(self.post.id,))
        self.assertRedirects(response, f'{lgn}?next={crt}')
