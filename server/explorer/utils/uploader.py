"""
Copyright 2015, Cisco Systems, Inc

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

@author: Pravin Gohite, Cisco Systems, Inc.
"""

import os
import sys
import glob
import logging
import tempfile
from sets import Set
import lxml.etree as ET
from explorer.utils.yang import Parser, Compiler
from explorer.utils.dygraph import DYGraph

def _get_session_path(session):
    """ Build path to session directory """

    return os.path.join('data', 'session', session)

def _get_yang_path(user):
    """ Build path to user's yang directory """

    return os.path.join('data', 'users', user, 'yang')

def _get_cxml_path(user):
    """ Build path to user's yang directory """
    return os.path.join('data', 'users', user, 'cxml')

def upload_file(_file, directory):
    """ Upload yang model into session storage """
    try:
        if not os.path.exists(directory):
            logging.debug('Creating session storage ..')
            os.makedirs(directory)

        if not os.path.exists(directory):
            logging.error('Failed to create session storage ..')
            return None

        logging.debug('Copying file content ..')
        f = tempfile.NamedTemporaryFile('w+', suffix='.py', dir=directory, delete=False)
        fname = f.name
        for chunk in _file.chunks():
            f.write(chunk)
        f.close()

        parser = Parser(fname)
        target_file = os.path.join(directory, parser.get_filename())
        os.rename(fname, target_file)
        logging.debug('Copied to ' + target_file)
    except:
        logging.error('Failed to upload file .. ' + sys.exc_info()[0])
        return None
    finally:
        logging.debug('Cleaning up ..')
        if os.path.exists(f.name):
            logging.debug('Deleting ' + f.name)
            os.remove(f.name)

    return parser.get_filename()

def sync_file(user, session, filename, index):
    """ Compile yang module """
    if index == '0':
        logging.debug('Compiling session dependency ...')
        Compiler.compile_pyimport(user, session)

    _file = os.path.join(_get_session_path(session), filename)
    if os.path.exists(_file):
        (rc, msgs) = Compiler.compile_cxml(user, session, _file)
    else:
        logging.error('sync_file: File %s not found ' % filename)
        (rc, msgs) = (False, None)
    return (rc, msgs)

def _compile_dependecies(user, modules):
    """ Compile affected modules """
    logging.debug('Compiling dependency ..')
    
    yangdst = _get_yang_path(user)
    dfile = os.path.join(yangdst, 'dependencies.xml')
    if not os.path.exists(dfile):
        logging.debug('Dependency file not found!!')
        return

    dmodules = Set([])
    dgraph = DYGraph(dfile)
    for m in modules:
        module = dgraph.dependency_module(m)
        if module is None:
            continue
        for name in module.imports:
            dmodules.add(name) 
        for name in module.depends:
            dmodules.add(name)

    dmodules_list = list(dmodules)
    for yangfile in glob.glob(os.path.join(yangdst, '*.yang')):
        basename = os.path.basename(yangfile)
        #skip dependency module itself
        if basename in modules:
            continue

        base = os.path.splitext(basename)[0]
        if '@' in base:
            base = base.split('@')[0]
        if base in dmodules_list:
            (rc, msgs) = Compiler.compile_cxml(user, None, yangfile)

def commit_files(user, session):
    """ Moves compiled yang moudles to user's yang directory """

    directory = _get_session_path(session)
    if not os.path.exists(directory):
        logging.error('Session storage %s does not exist' % directory)
        return (False, None)

    yangdst = _get_yang_path(user)
    cxmldst = _get_cxml_path(user)
    count = 0

    if not os.path.exists(yangdst):
        logging.debug('Created ' + yangdst)
        os.makedirs(yangdst)

    if not os.path.exists(cxmldst):
        logging.debug('Created ' + cxmldst)
        os.makedirs(cxmldst)
    
    modules = ET.Element('modules')
    for cxmlpath in glob.glob(os.path.join(directory, '*.xml')):
        basename = os.path.basename(cxmlpath)
        if basename == 'dependencies.xml':
            continue
        base = os.path.splitext(basename)[0]
        yang_src_path = os.path.join(directory, base + '.yang')
        yang_dst_path = os.path.join(yangdst, base + '.yang')
        cxml_dst_path = os.path.join(cxmldst, base + '.xml')
        logging.debug('Committing ' + yang_src_path)
        if os.path.exists(yang_src_path):
            logging.debug('Commit ' + yang_dst_path)
            os.rename(yang_src_path, yang_dst_path)
            os.rename(cxmlpath, cxml_dst_path)
            module = ET.Element('module')
            module.text = base + '.yang'
            modules.append(module)
            count += 1

    # There is a update in yang modules, delete existing dependency file
    # so that it will be recompiled next time
    if count > 0:
        session_d = os.path.join(directory, 'dependencies.xml')
        if os.path.exists(session_d):
            logging.debug('Moving dependency file ...')
            os.rename(session_d, os.path.join(yangdst, 'dependencies.xml'))
        else:
            logging.debug('Compiling user dependency ...')
            Compiler.compile_pyimport(user)

        # added module might affect existing module, recompile them
        _compile_dependecies(user, [m.text for m in modules])
    
    logging.debug('Committed ' + str(count) + ' file(s)')
    return (True, modules)

def get_upload_files(user, session):
    """ Get the list of uploaded yang files which are not committed """

    directory = _get_session_path(session)
    if not os.path.exists(directory):
        logging.error('Session storage %s does not exist' % directory)
        return (False, None)

    modules = ET.Element('modules')
    for _file in glob.glob(os.path.join(directory, '*.yang')):
        module = ET.Element('module')
        module.text = os.path.basename(_file)
        modules.append(module)

    return (True, modules)

def clear_upload_files(user, session):
    """ Delete uploaded yang files which are not committed """

    directory = _get_session_path(session)
    if not os.path.exists(directory):
        logging.error('Session storage %s does not exist' % directory)
        return (False, None)

    modules = ET.Element('modules')
    for _file in glob.glob(os.path.join(directory, '*')):
        os.remove(_file)

    return (True, modules)


