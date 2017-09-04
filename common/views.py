from django.db.models import Q
from django.conf import settings
from django.shortcuts import render
from django.views.generic import TemplateView, ListView
from django.core.urlresolvers import reverse_lazy
from django.contrib.auth.mixins import AccessMixin
from django.views.generic.base import ContextMixin

from common.utils import get_value

from article.models import Article, Comment
from article.filters import ArticleFilter
from banner.models import Banner
from navbar.models import NavBar
from link.models import Link

# logger
import logging

logger = logging.getLogger("info")


class BaseContextMixin(ContextMixin):
    def get_context_data(self, *args, **kwargs):
        try:
            # 网站标题等内容
            kwargs['website_title'] = get_value(settings.WEBSITE_TITLE)
            kwargs['website_welcome'] = get_value(settings.WEBSITE_WELCOME)
            # SEO
            kwargs['website_seo_keyword'] = get_value(settings.WEBSITE_SEO_KEYWORD)
            kwargs['website_seo_description'] = get_value(settings.WEBSITE_SEO_DESCRIPTION)
            # 导航条
            kwargs['nav_list'] = NavBar.objects.all()
            if hasattr(self, 'request'):
                # 用户未读消息数
                user = self.request.user
                if user.is_authenticated():
                    kwargs['notification_count'] = user.to_user_notification_set.filter(is_read=0).count()
                    kwargs['can_add_article'] = user.has_perm('article.add_article')
                    kwargs['can_change_article'] = user.has_perm('article.change_article')
                # 搜索框默认输入选项
                kwargs['search'] = self.request.GET.get('search', '')
        except Exception as e:
            logger.error(u'[BaseContextMixin]加载基本信息出错 {}'.format(e))
        return super(BaseContextMixin, self).get_context_data(**kwargs)


class BaseMixin(BaseContextMixin):
    def get_queryset(self):
        articles = Article.public.filter(status=0).all()

        if hasattr(self, 'request'):
            if self.request.user.has_perm('article.view_article'):
                articles = Article.objects.all()
            if 'search' in self.request.GET:
                search = self.request.GET.get('search')
                articles = articles.filter(
                    Q(title__icontains=search) |
                    Q(summary__icontains=search) |
                    Q(tags__icontains=search)
                )
            articles = ArticleFilter(self.request.GET, queryset=articles).qs
        return articles.order_by('-is_top', '-publish_time')

    def get_context_data(self, *args, **kwargs):
        try:
            articles = self.get_queryset()
            # 热门文章
            kwargs['hot_article_list'] = articles.order_by("-view_times")[:10]
            # 最新评论
            kwargs['latest_comment_list'] = Comment.objects.filter(article__in=articles).order_by("-id")[0:6]
            # 友情链接
            kwargs['links'] = Link.objects.order_by('create_time').all()
            colors = ['primary', 'success', 'info', 'warning', 'danger']
            for index, link in enumerate(kwargs['links']):
                link.color = colors[index % len(colors)]
        except Exception as e:
            logger.error(u'[BaseMixin]加载基本信息出错 {}'.format(e))
        return super(BaseMixin, self).get_context_data(**kwargs)


class ModelPermission(AccessMixin):
    action = 'view'
    raise_exception = True
    login_url = reverse_lazy('user_login')
    permission_denied_message = '您无权查看此项信息，如有疑问请联系管理员。'

    def dispatch(self, request, *args, **kwargs):
        if self.action == 'add' and request.user.has_perm('article.add_article'):
            pass
        elif self.action == 'change' and request.user.has_perm('article.change_article'):
            pass
        elif self.action == 'delete' and request.user.has_perm('article.delete_article'):
            pass
        else:
            return self.handle_no_permission()
        return super(ModelPermission, self).dispatch(request, *args, **kwargs)


class IndexView(BaseMixin, ListView):
    template_name = 'index.html'
    context_object_name = 'article_list'
    paginate_by = settings.PAGE_NUM

    def get_context_data(self, **kwargs):
        # 轮播
        kwargs['banner_list'] = Banner.objects.all()
        return super(IndexView, self).get_context_data(**kwargs)


class VersionView(BaseContextMixin, TemplateView):
    template_name = 'common/version.html'

    def get_context_data(self, **kwargs):
        # 查看站点流量
        kwargs['can_view_cnzz'] = self.request.user.has_perm('user.view_cnzz')
        return super(VersionView, self).get_context_data(**kwargs)


# 400页面
def bad_request(request):
    base_context_mixin = BaseContextMixin()
    base_context_mixin.request = request
    context = base_context_mixin.get_context_data()
    return render(request, '400.html', context, status=400)


# 403页面
def permission_denied(request):
    base_context_mixin = BaseContextMixin()
    base_context_mixin.request = request
    context = base_context_mixin.get_context_data()
    return render(request, '403.html', context, status=403)


# 404页面
def page_not_found(request):
    base_context_mixin = BaseContextMixin()
    base_context_mixin.request = request
    context = base_context_mixin.get_context_data()
    return render(request, '404.html', context, status=404)


# 500页面
def server_error(request):
    base_context_mixin = BaseContextMixin()
    base_context_mixin.request = request
    context = base_context_mixin.get_context_data()
    return render(request, '500.html', context, status=500)
