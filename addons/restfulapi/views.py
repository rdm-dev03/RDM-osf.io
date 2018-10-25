# -*- coding: utf-8 -*-

import requests
import logging
import json
import time
import os
import shutil
import subprocess
from celery.result import AsyncResult
from framework.celery_tasks import app as celery_app
from framework.sessions import session
from flask import request
from api.base.utils import waterbutler_api_url_for
from website.project.decorators import (
    must_be_contributor_or_public,
    must_have_addon,
    must_be_valid_project,
    must_not_be_retracted_registration,
)


@must_be_valid_project
@must_be_contributor_or_public
@must_have_addon('restfulapi', 'node')
@must_not_be_retracted_registration
def restfulapi_download(auth, **kwargs):
    uid = auth.user._id
    data = request.get_json()

    prevalidation_result = prevalidate_data(data)
    if not prevalidation_result['valid']:
        return {
            'status': 'Failed',
            'message': prevalidation_result['message']
        }

    # Clean up input
    data['url'] = data['url'].strip().split(' ')[0]

    postvalidation_result = postvalidate_data(data)
    if not postvalidation_result['valid']:
        return {
            'status': 'Failed',
            'message': postvalidation_result['message']
        }

    if u'restfulapi' not in session.data:
        session.data[u'restfulapi'] = {}
    if u'task_list' not in session.data[u'restfulapi']:
        session.data[u'restfulapi'][u'task_list'] = []

    task = main_task.delay(request.cookies.get('osf'), uid, data)
    session.data[u'restfulapi'][u'task_list'].append(task.task_id)
    session.save()

    return {
        'status': 'OK',
    }

@must_be_valid_project
@must_be_contributor_or_public
@must_have_addon('restfulapi', 'node')
@must_not_be_retracted_registration
def restfulapi_cancel(auth, **kwargs):
    return {
        'status': 'OK',
        'message': 'Download task has been cancelled.'
    }

def prevalidate_data(data):
    '''
    Check if the required fields are filled.
    '''
    if not data['url']:
        return {
            'valid': False,
            'message': 'Please specify an URL.'
        }
    if not data['pid']:
        return {
            'valid': False,
            'message': 'Please specify the destination to save the file(s).'
        }
    return {
        'valid': True,
    }

def postvalidate_data(data):
    '''
    Check if URL responds to requests.
    '''
    response = None
    try:
        response = requests.head(data['url'])
    except Exception:
        return {
            'valid': False,
            'message': 'An error ocurred while accessing the URL.'
        }
    # Sometimes there are false negatives (status code 500)
    # Likely such requests are not implemented on servers
    if response.status_code >= 400 and response.status_code != 500:
        return {
            'valid': False,
            'message': 'URL returned an invalid response.'
        }
    return {
        'valid': True,
    }

@celery_app.task
def main_task(osf_cookie, uid, data):
    '''
    Creates a temporary folder to download the files from the inputted URL,
    downloads from it, uploads to the selected storage and deletes the temporary
    files.
    '''
    tmp_path = create_tmp_folder(uid)
    if not tmp_path:
        raise OSError('Could not create temporary folder.')

    downloaded = get_files(tmp_path, data)
    if not downloaded:
        raise RuntimeError('wget command returned a non-success code.')

    dest_path = 'osfstorage/' if 'folderId' not in data else data['folderId']
    uploaded = upload_folder_content(osf_cookie, data['pid'], tmp_path, dest_path)
    shutil.rmtree(tmp_path)
    if not uploaded:
        raise RuntimeError('wget command returned a non-success code.')

    return True

def create_tmp_folder(uid):
    '''
    Creates a temporary folder to download the files into.
    '''
    full_path = None
    try:
        if not os.path.isdir('tmp'):
            os.mkdir('tmp')
        if not os.path.isdir('tmp/restfulapi'):
            os.mkdir('tmp/restfulapi')
        count = 1
        folder_name = '%s_%s' % (uid, int(time.time()))
        while os.path.isdir('tmp/restfulapi/' + folder_name):
            count += 1
            folder_name = '%s_%s_%s' % (uid, int(time.time()), count)
        full_path = 'tmp/restfulapi/' + folder_name
        os.mkdir(full_path)
    except Exception:
        full_path = None
    return full_path

def get_files(tmp_path, data):
    '''
    Download the files from the RESTfulAPI URL provided by the user.
    '''
    command = ['wget', '-P', tmp_path]
    if data['recursive']:
        command.append('-r')
    if data['interval']:
        command += ['-w', data['intervalValue']]
    command.append(data['url'])
    return_value = subprocess.call(command)
    return return_value == 0

@celery_app.task
def upload_folder_content(osf_cookie, pid, path, dest_path):
    '''
    Upload all the content (files and folders) inside a folder.
    '''
    content_list = os.listdir(path)

    for item_name in content_list:
        full_path = os.path.join(path, item_name)
        if os.path.isdir(full_path):  # Create directory
            folder = create_folder(osf_cookie, pid, item_name, dest_path)
            if folder['success']:
                upload_folder_content(osf_cookie, pid, full_path, folder['id'])
        else:  # File
            upload_file(osf_cookie, pid, full_path, item_name, dest_path)

    return True

@celery_app.task
def create_folder(osf_cookie, pid, folder_name, dest_path):
    dest_arr = dest_path.split('/')
    response = requests.put(
        waterbutler_api_url_for(
            pid, dest_arr[0], path='/' + os.path.join(*dest_arr[1:]),
            name=folder_name, kind='folder', meta='', _internal=True
        ),
        cookies={
            'osf': osf_cookie
        }
    )
    if response.status_code == requests.codes.created:
        data = response.json()
        return {
            'success': True,
            'id': data['data']['id']
        }
    return {
        'success': False
    }

@celery_app.task
def upload_file(osf_cookie, pid, file_path, file_name, dest_path):
    response = None
    dest_arr = dest_path.split('/')
    with open(file_path, 'r') as f:
        response = requests.put(
            waterbutler_api_url_for(
                pid, dest_arr[0], path='/' + os.path.join(*dest_arr[1:]),
                name=file_name, kind='file', _internal=True
            ),
            data=f,
            cookies={
                'osf': osf_cookie
            }
        )
    return response