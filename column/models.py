from django.db import models
from django.urls import reverse


# 专栏
class Column(models.Model):
    # 专栏名称
    name = models.CharField(max_length=40,
                            verbose_name='专栏名称')
    # 专栏摘要
    summary = models.TextField(verbose_name='专栏摘要')
    # 文章
    article = models.ManyToManyField('article.Article',
                                     verbose_name='文章')
    # 创建时间
    create_time = models.DateTimeField(auto_now_add=True,
                                       verbose_name='创建时间')

    class Meta:
        verbose_name_plural = verbose_name = '专栏'
        ordering = ['-create_time']

    def get_absolute_url(self):
        return reverse('column_detail', args=(self.name,))

    def __str__(self):
        return self.name
