#coding:utf-8
from django.shortcuts import render, HttpResponse, redirect
import json, qcloud_cos
from BeautifulSoup import BeautifulSoup
from blog.models import Search_record
import re, requests
from config import (
    APP_ID,
    SecretID,
    SecretKey
)
from uuid import uuid1
from django.http import JsonResponse
from django_web.timehelper import datetime2timestamp
from datetime import datetime
from blog.models import ZoneSubject
from django.views.decorators.csrf import csrf_exempt
import requests
import memcache, qcloud_cos, json
from django.contrib.auth.models import User
from django.contrib import auth
from blog.models import Article, Comment
from django.contrib.auth.decorators import login_required
mc = memcache.Client(['localhost:11211'])



def test(request):
    return HttpResponse('User-agent: *\nAllow: /')

def sign(request):
    sign_type = request.GET.get('sign_type', '')
    bucketName = 'image'
    qcloud_cos.conf.set_app_info(APP_ID, SecretID, SecretKey)
    auth = qcloud_cos.Auth(SecretID, SecretKey)
    if sign_type == 'appSign':
        if 'expired' not in request.GET:
            return JsonResponse(dict(code=10001,message=u"缺少expired"))
        expired = request.GET.get('expired', '')
        sign = auth.sign_more(bucketName, expired)
        return HttpResponse(json.dumps(dict(
            code="0", message=u'成功', data={'sign': sign}, key=str(uuid1())
        )))
    elif sign_type == 'appSign_once':
        path = request.GET.get('path')
        sign = auth.sign_once('image', path)
        return HttpResponse(json.dumps(dict(
            code="0", message=u'成功', data={'sign': sign}, key=str(uuid1())
        )))
    else:
        return JsonResponse(code=10001, message=u'未指定签名方式')


def upload_api(request):
    last_time = request.session.get('time', None)
    if last_time:
        time_limit = datetime2timestamp(datetime.utcnow())-last_time
        if time_limit/1000 < 5:
            return JsonResponse(dict(stat=0, message='上传太过频繁！'))
    title = request.POST.get('title', '')
    content = request.POST.get('content', None)
    if content:
        if len(title)> 15:
            return JsonResponse(dict(stat=0, message='标题长度不合适'))
        create_time = datetime.utcnow()
        zone = ZoneSubject(
            title=title,
            image_url=content,
            create_time=create_time
        )
        zone.save()
        request.session['time'] = datetime2timestamp(datetime.utcnow())
        return JsonResponse(dict(stat=1, message='上传成功！'))

def return_zhihu_img(request):

    img_url = str(request.GET['url'])
    img_cache = mc.get(img_url)
    if img_cache:
        return_img = img_cache
    else:
        header = {'Referer':img_url,'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36',
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',':host':'pic1.zhimg.com'
        }
        r = requests.get(img_url)
        return_img = r.content
        mc.set(img_url, r.content, 60*60*24)
    return HttpResponse(return_img, content_type='image/jpeg')

def return_douban_img(request):
    img_url = str(request.GET['url'])
    img_cache = mc.get(img_url)
    if img_cache:
        return_img = img_cache
    else:
        header = {'Referer':img_url,'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36',
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        r = requests.get(img_url)
        return_img = r.content
        mc.set(img_url, r.content, 60*60*24)
    return HttpResponse(return_img, content_type='image/jpeg')

def insert_search(request):
    url = request.GET.get('url', None)
    if url:
        if re.compile(r"(http|https)://www.zhihu.com/question/\d{8}").match(url) or \
            re.compile(r"(http|https)://www.zhihu.com/collection/\d{8}").match(url) :
            find_item = Search_record.objects.filter(url=url)
            if len(find_item) == 0:
                r = requests.get(url)
                soup = BeautifulSoup(r.content)
                title = soup.title.string
                search_item = Search_record(
                    title=title,
                    url=url,
                    searchCount=0

                )
                try:
                    search_item.save()
                except Exception,e:
                    import sys
                    print>>sys.stderr, e
                return JsonResponse(dict(stat=1, message=u'提交成功，系统正在抓取，请过一段时间再来查看'))
            else:
                return JsonResponse(dict(stat=0, message=u'该链接已存在！'))
        else:
            return JsonResponse(dict(stat=0, message=u'链接格式出错'))


def login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    else:
        username = request.POST.get('username', None)
        pwd = request.POST.get('password', None)
        next = request.GET.get('next', None)
        print next
        if username and pwd:
            user = auth.authenticate(username=username, password=pwd)
            if user:
                auth.login(request, user)
                if next:
                    return JsonResponse(dict(stat=1, msg=u'登录成功！', url=next))
                else:
                    return JsonResponse(dict(stat=1, msg=u'登录成功！', url='/'))
            else:
                return JsonResponse(dict(stat=0, msg=u'用户名密码错误！'))
        else:
            return JsonResponse(dict(stat=0, msg=u'请输入用户名密码！'))

def logout(request):
    if request.method == 'GET':
        auth.logout(request)
        return redirect('/accounts/login')

def resister(request):
    if request.method == 'GET':
        return render(request, 'register.html')
    else:
        username = request.POST.get('username', None)
        pwd = request.POST.get('password', None)
        email = request.POST.get('email', None)
        if username and pwd and email:
            try:
                user = User.objects.create_user(username=username, password=pwd, email=email)
                user.save()
                return JsonResponse(dict(stat=1, msg=u'注册成功！'))
            except Exception, e:
                return JsonResponse(dict(stat=0, msg=u'用户名已存在！'))
        else:
            return JsonResponse(dict(stat=0, msg=u'参数错误！'))

@login_required
def push_comment(request):
    if request.method == 'POST':
        article_id = request.GET.get('article_id', None)
        content = request.POST.get('content', '')
        if len(content) > 0:
            user = auth.get_user(request)
            find_article =  Article.objects.get(id=article_id)
            comment = Comment(
                article=find_article,
                content=content,
                user_id=user.id
            )
            comment.save()
            return JsonResponse(dict(stat=1, msg=u'发表成功！'))
