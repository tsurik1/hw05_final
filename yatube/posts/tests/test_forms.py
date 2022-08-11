from django.test import Client, TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from ..models import Group, Post, User, Comment, Follow


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

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_count_post(self):
        """Валидная форма создает запись в Post."""
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
        """Проверка редактирования поста."""
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

    def test_redirect(self):
        """Проверка перенаправления"""
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

    def test_redirect_client_to_login(self):
        """Проверка перенаправления клиента на логин."""
        posts_count = Post.objects.count()
        response = self.guest_client.post(
            reverse('posts:create_post'), follow=True
        )
        lgn = reverse('users:login')
        crt = reverse('posts:create_post')
        self.assertRedirects(response, f'{lgn}?next={crt}')
        self.assertEqual(Post.objects.count(), posts_count)

    def test_only_authorized_user_can_comment(self):
        """Проверка: пост может комментировать только авторизованный."""
        form_data = {
            'text': 'test comment',
        }
        response = self.client.post(reverse(
            'posts:add_comment', args=(self.post.id,)), data=form_data
        )
        self.assertEqual(response.status_code, 302)

    def test_after_submitting_the_comment_appears_on_the_page(self):
        """Проверка: после отправки коммент появляется на стр."""
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

    def test_an_authorized_user_can_follow_or_ufollow(self):
        """Авторизованный пользователь может подписываться и отписываться."""
        follows_count = Follow.objects.count()
        pypa = User.objects.create_user(username='pypa')
        self.authorized_client = Client()
        self.authorized_client.force_login(pypa)
        self.authorized_client.get(
            reverse('posts:profile_follow', args=(self.user.username,)),
            follow=True)
        self.assertEqual(Follow.objects.count(), follows_count + 1)
        self.authorized_client.get(
            reverse('posts:profile_unfollow', args=(self.user.username,)),
            )  
        self.assertEqual(Follow.objects.count(), follows_count)

    def test_user_feed(self):
        """Новая запись появляется в ленте подписчиков"""
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
