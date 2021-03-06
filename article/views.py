import ast
import json
import datetime

from django.db.models import Count
from django.core.cache import caches
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, Http404
from django.template.loader import get_template
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.context_processors import PermWrapper
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView

from common.views import BaseMixin
from common.utils import get_ip
from notification.models import Notification

from .forms import *
from .models import *
from .filters import *

# logger
import logging

logger = logging.getLogger("info")

# 缓存
try:
    cache = caches['memcache']
except ImportError as e:
    cache = caches['default']


class ArticleIndexView(BaseMixin, ListView):
    template_name = 'article/index.html'
    context_object_name = 'article_list'
    paginate_by = settings.PAGE_NUM
    search_fields = ('name',)


# 新建博客
class ArticleCreateView(PermissionRequiredMixin, BaseMixin, CreateView):
    permission_required = ('article.add_article',)
    raise_exception = True
    form_class = ArticleForm
    template_name = 'article/create.html'

    def form_valid(self, form):
        instance = form.save()
        instance.author = self.request.user
        instance.save()
        self.success_url = reverse('article_detail', kwargs={'pk': instance.id})
        return super(ArticleCreateView, self).form_valid(form)


# 更新博客
class ArticleUpdateView(PermissionRequiredMixin, BaseMixin, UpdateView):
    permission_required = ('article.change_article',)
    raise_exception = True
    form_class = ArticleForm
    success_url = '/'
    template_name = 'article/update.html'

    def form_valid(self, form):
        instance = form.save()
        self.success_url = reverse('article_detail', kwargs={'pk': instance.id})
        return super(ArticleUpdateView, self).form_valid(form)


# 博客详情
class ArticleDetailView(BaseMixin, DetailView):
    template_name = 'article/detail.html'
    context_object_name = 'article'

    def get(self, request, *args, **kwargs):
        article = self.get_object()
        # 统计文章的访问访问次数
        ip = get_ip(request)
        # 获取15*60s时间内访问过这篇文章的所有ip
        visited_ips = cache.get(article.id, [])
        # 如果ip不存在就把文章的浏览次数+1
        if ip not in visited_ips:
            article.view_times += 1
            article.save()
            # 更新缓存
            visited_ips.append(ip)
            cache.set(article.id, visited_ips, 15 * 60)
        return super(ArticleDetailView, self).get(request, *args, **kwargs)


class AllView(BaseMixin, ListView):
    template_name = 'article/all.html'
    context_object_name = 'article_list'
    paginate_by = settings.PAGE_NUM

    def get_context_data(self, **kwargs):
        kwargs['nav_index'] = 'all'
        kwargs['category_list'] = Category.objects.all()
        kwargs['PAGE_NUM'] = settings.PAGE_NUM
        return super(AllView, self).get_context_data(**kwargs)

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset().order_by('-publish_time')
        context = self.get_context_data()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        val = self.request.POST.get("val", "")
        sort = self.request.POST.get("sort", "-publish_time")
        start = int(self.request.POST.get("start", 0))
        end = int(self.request.POST.get("end", settings.PAGE_NUM))

        if val == 'all':
            category_list = Category.objects.all()
        else:
            category_list = Category.objects.filter(name=val).all()
        article_list = self.get_queryset().filter(category__in=category_list).annotate(
            comment_count=Count('comment_article')).order_by(sort).all()[start:end + 1]

        is_end = len(article_list) != (end - start + 1)
        article_list = article_list[0:end - start]

        html = ""
        for article in article_list:
            html += get_template('article/article_item.html').render({'article': article,
                                                                      'perms': PermWrapper(request.user)})

        _dict = {"html": html, "isend": is_end}
        return HttpResponse(
            json.dumps(_dict),
            content_type="application/json"
        )


class CommentControl(BaseMixin, View):
    def post(self, request, *args, **kwargs):
        user = request.user

        if user.is_authenticated:
            pk = self.kwargs.get('pk', '')
            try:
                article = self.get_queryset().get(id=pk)
            except ObjectDoesNotExist:
                raise Http404

            text = request.POST.get("comment", "")
            if text:
                parent = None
                if text.startswith('@['):
                    parent_str = text[1:text.find(':')]
                    parent_id = ast.literal_eval(parent_str)[1]
                    text = text[text.find(':') + 2:]
                    try:
                        parent = Comment.objects.get(pk=parent_id)
                        info = '{}回复了你在 {} 的评论'.format(user.username, parent.article.title)
                        Notification.objects.create(title=info, text=text, from_user=user, to_user=parent.user,
                                                    url='/article/{}/'.format(pk))
                    except Comment.DoesNotExist:
                        return HttpResponse("请勿修改评论代码！", status=403)

                comment = Comment.objects.create(user=user, article=article, text=text, parent=parent)

                comment_code = "<p>评论：{}</p>".format(text)
                if parent:
                    comment_code = "<div class=\"comment-quote\">\
                                         <p>\
                                             <a>@{}</a>\
                                             {}\
                                         </p>\
                                     </div>".format(parent.user.username, parent.text) + comment_code
                # 返回当前评论
                html = "<li>\
                           <div class=\"comment-tx\">\
                               <img src='{}' width=\"40\"></img>\
                           </div>\
                           <div class=\"comment-content\">\
                               <a><h1>{}</h1></a>\
                               {}\
                               <p>{}</p>\
                           </div>\
                       </li>".format(comment.user.get_portrait(), comment.user.username, comment_code,
                                     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                return HttpResponse(html)
            else:
                return HttpResponse("请输入评论内容！", status=403)
        else:
            return HttpResponse("请登录！", status=403)
