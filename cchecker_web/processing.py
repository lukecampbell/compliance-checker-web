#!/usr/bin/env python

from compliance_checker.runner import CheckSuite
from rq.connections import get_current_connection
import base64
import logging
import requests
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def compliance_check(job_id, dataset, checker):
    try:
        cs = CheckSuite()
        if dataset.startswith('http'):
            dataset = check_redirect(dataset)
        ds = cs.load_dataset(dataset)
        redis = get_current_connection()
        score_groups = cs.run(ds, checker)

        rpair = score_groups[checker]
        groups, errors = rpair

        aggregates = cs.build_structure(checker, groups, dataset)
        aggregates = cs.serialize(aggregates)
        # We use b64 to keep the filenames safe but it's helpful to the user to see
        # the filename they uploaded
        if not aggregates['source_name'].startswith('http'):
            aggregates['source_name'] = base64.b64decode(aggregates['source_name'].split('/')[-1])
        buf = json.dumps(aggregates)

        redis.set('processing:job:%s' % job_id, buf, 3600)
        return True
    except Exception as e:
        redis.set('processing:job:%s' % job_id, json.dumps({"error":type(e).__name__, "message":e.message}), 3600)
        return False

def check_redirect(dataset, checked_urls=None):
    checked_urls = checked_urls or []
    if dataset in checked_urls:
        raise IOError("Invalid URL")
    checked_urls.append(dataset)
    response = requests.get(dataset + '.das', allow_redirects=False)
    if response.status_code == 301:
        new_location = response.headers['Location']
        new_location = new_location.replace('.das','')
        return check_redirect(new_location, checked_urls)
    return dataset
