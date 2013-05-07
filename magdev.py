# vim: set fileencoding=utf-8 :
from __future__ import absolute_import, division

import os
from pkg_resources import resource_filename
from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    UndefinedError,
)
from ConfigParser import (
    SafeConfigParser,
)
import subprocess
import tempfile
import shutil
import logging
from contextlib import contextmanager
from collections import defaultdict

__version__ = (0, 1, 0)

DEFAULT_CONFIG = {}

# Setup logger
log = logging.getLogger('magdev')
handler = logging.StreamHandler()
log.addHandler(handler)
log.setLevel(logging.INFO)


def tree():
    return defaultdict(tree)


class BaseError(Exception):
    pass


class Config(SafeConfigParser):
    """Config class"""

    def get_extensions(self):
        """Get extensions config

        :returns: A tree
        """
        extensions = tree()
        if self.has_section('extensions'):
            for k in self.options('extensions'):
                k_parts = k.split('.')
                if len(k_parts) < 2:
                    continue
                if len(k_parts) == 2:
                    extensions[k_parts[0]][k_parts[1]] = self.get('extensions',
                                                                  k)
                # ignore others

        # TODO: Assert that all required stuff is set
        # TODO: Assert that name only contains /a-z_/i
        return extensions


def git_call(args, cwd=None):
    """Make a git call

    :param args: list of git arguments
    :param cwd: working directory for the call

    :returns: The subprocess stdout
    """
    try:
        return subprocess.check_output(['git'] + args,
                                       cwd=cwd,
                                       shell=False
                                       )
    except subprocess.CalledProcessError, e:
        log.info(e.output)
        raise e


@contextmanager
def download_git_repo(uri):
    """Download a git repo

    yields the temporary download dir, on exit it will be deleted

    :param uri: URI string(Will be split on space so it can contain git flags)

    """
    build_dir = tempfile.mkdtemp('magdev')
    repo_dir = os.path.join(build_dir, 'repo')
    git_call(['clone'] + [s for s in uri.split(' ') if s.strip] + [repo_dir])

    yield repo_dir
    shutil.rmtree(build_dir)


class Magdev():

    template_suffix = '.jinja2'

    def __init__(self, path):
        self.path = os.path.abspath(path)

    @property
    def magento_dir(self):
        return os.path.join(self.path, 'magento')

    @property
    def extensions_dir(self):
        return os.path.join(self.path, 'extensions')

    @property
    def config_dir(self):
        return os.path.join(self.magento_dir, '.magdev')

    @property
    def config_file_path(self):
        return os.path.join(self.config_dir, 'magdev.ini')

    @property
    def config(self):
        path = self.config_file_path
        defaults = DEFAULT_CONFIG.copy()
        defaults['here'] = self.path
        config = Config(defaults)
        config.read(path)
        return config

    def exists(self):
        """Check if this magdev project exists"""
        return os.path.isfile(self.config_file_path)

    def init(self, template_vars):
        """Init this magdev

        Will create the git repo.

        Required template_vars:

            * ['magento']['git']

        :param template_vars: Variables that will be set for the templates.

        :returns: Nothing
        """
        assert not self.exists()
        os.makedirs(self.magento_dir, 0755)
        os.makedirs(self.config_dir, 0755)
        os.makedirs(self.extensions_dir, 0755)

        # Copy files from data
        data_dir = os.path.abspath(resource_filename(__name__, 'data'))
        env = Environment(loader=FileSystemLoader(data_dir),
                          undefined=StrictUndefined)
        dest_dir = self.config_dir

        for rel_root, dirs, files in os.walk(data_dir):
            root = os.path.abspath(rel_root)
            template_base = root[len(data_dir) + 1:]

            for f in files:
                if f.endswith(self.template_suffix):
                    src = os.path.join(template_base, f)
                    dest = os.path.join(dest_dir,
                                        template_base,
                                        f[0:-len(self.template_suffix)])

                    # Get contents before truncating the file
                    try:
                        contents = env.get_template(src).render(
                            **template_vars)
                    except UndefinedError, e:
                        raise BaseError("Template error {0} (in '{1}')"
                                        .format(e, src))

                    with open(dest, 'w') as fh:
                        fh.write(contents)
                else:
                    src = os.path.join(root, f)
                    dest = os.path.join(dest_dir, template_base, f)
                    shutil.copyfile(src, dest)
            for d in dirs:
                dest = os.path.join(dest_dir,
                                    template_base,
                                    d)
                if not os.path.isdir(dest):
                    os.makedirs(dest)

        self.update_ignore_file()
        self._git(['init'])
        self._git(['add', '.'])
        self._git(['commit', '-m', 'Base Magdev project'])

        # Update magento and commit that update
        self.update_magento()
        self._git(['add', '.'])
        self._git(['commit', '-m', 'Added magento'])

        # Update extensions
        self.update_extensions()

    def clone(self, uri):
        """Clone from uri"""
        assert not self.exists()
        os.makedirs(self.path)
        git_call(['clone'] + [l for l in uri.split(' ') if l.strip()] +
                 [self.magento_dir])

    def _git(self, args):
        """Run a git command on the repo"""
        return git_call(args, self.magento_dir)

    def _git_modified(self):
        return 'nothing to commit, working directory clean' \
                not in self._git(['st'])

    def _git_clean(self):
        """Clean git repo, including ignored files"""
        return self._git(['clean', '-f', '-d', '-x'])

    def update_all(self):
        self.update_magento()
        self.update_extensions()

    def update_magento(self):
        """Update magento

        """

        if self._git_modified():
            raise BaseException("Cannot update magento - repo is modified")
        self._git_clean()

        log.info('Updating magento')

        # TODO: Remove old magento files by using git
        dest_dir = self.magento_dir
        with download_git_repo(self.config.get('magento', 'git')) as src_dir:
            # Move magento files
            for rel_root, dirs, files in os.walk(src_dir):
                if '.git' in rel_root:
                    continue
                root = os.path.abspath(rel_root)
                rel_base = root[len(src_dir) + 1:]
                for f in files:
                    if f.startswith('.git'):
                        continue
                    shutil.copy2(os.path.join(src_dir, rel_base, f),
                                 os.path.join(dest_dir, rel_base, f))
                for d in dirs:
                    if d.startswith('.git'):
                        continue
                    src = os.path.join(src_dir, rel_base, d)
                    dest = os.path.join(dest_dir, rel_base, d)
                    if not os.path.isdir(dest):
                        # preserve permissions
                        os.makedirs(dest, os.stat(src).st_mode & 0777)

        files = ['/{0}'.format(f) for f in os.listdir(self.magento_dir)
                 if not f.startswith('.git')]

        self.write_ignore_file('magento', files)
        self.update_ignore_file()

    def write_ignore_file(self, name, files):
        with open(os.path.join(self.config_dir, 'ignore', name), 'w') as fh:
            fh.write("\n".join(files))

    def update_ignore_file(self):
        ignores = []
        unignores = []
        ignore_dir = os.path.join(self.config_dir, 'ignore')
        unignore_dir = os.path.join(self.config_dir, 'unignore')

        for name in os.listdir(ignore_dir):
            with open(os.path.join(ignore_dir, name), 'r') as fh:
                ignores.extend(['# .magdev/ignore/{0}'.format(name)] +
                               [l for l in fh.read().splitlines()
                                if not l.startswith('#')])

        for name in os.listdir(unignore_dir):
            with open(os.path.join(unignore_dir, name), 'r') as fh:
                unignores.extend(['# .magdev/unignore/{0}'.format(name)] +
                                 ["!{0}".format(l) for l
                                  in fh.read().splitlines()
                                  if not l.startswith('#')])

        with open(os.path.join(self.magento_dir, '.gitignore'), 'w') as f:
            f.write("# Autogenerated by magdev. Do not edit by hand\n"
                    "# Add files to ignore in .magdev/ignore\n"
                    "# Add files to un-ignore in .magdev/unignore\n")
            f.write("\n# Ignore files\n\n")
            f.write("\n".join(ignores))
            f.write("\n\n# Unignore files\n\n")
            f.write("\n".join(unignores))

    def update_extensions(self):
        log.info('Updating extensions')

        if not os.path.exists(self.extensions_dir):
            os.makedirs(self.extensions_dir)

        extensions = self.config.get_extensions()
        for (name, args) in extensions.iteritems():
            # Clone extension to extensions_dir
            repo_dir = os.path.join(self.extensions_dir, name)
            if os.path.exists(repo_dir):
                # Check if modified
                if 'nothing to commit, working directory clean' not in \
                        git_call(['st'], repo_dir):
                    raise BaseException("Will not pull extension {0} - "
                                        "modified".format(name))
                git_call(['pull'], repo_dir)
            else:
                git_call(['clone'] + [l for l in args['git'].split(' ')
                                      if l.strip()] + [repo_dir])
            # Symlink extension(Currently the only supported extension-type)
            self._symlink_extension(name)

    def _symlink_extension(self, extension_name):
        """Setup extension symlinks

        The symlinks will be relative, it will not remove old symlinks.

        :raises: `BaseException` If a symlink file already exists
        """

        repo_dir = os.path.join(self.extensions_dir, extension_name)

        ignore_files = []

        def _symlink(rel_dir):
            src_dir = os.path.join(repo_dir, rel_dir)
            dest_dir = os.path.join(self.magento_dir, rel_dir)
            symlinks = []
            for name in [f for f in os.listdir(src_dir)
                         if not f.startswith('.')]:
                src = os.path.join(src_dir, name)
                dest = os.path.join(dest_dir, name)
                # TODO: Use OS escape, not '/'
                link_target = os.path.join('../' * (rel_dir.count('/') + 2 if
                                                    rel_dir else 1),
                                           'extensions',
                                           extension_name,
                                           rel_dir,
                                           name)
                if os.path.lexists(dest):
                    if os.path.islink(dest):
                        old_link_target = os.path.abspath(
                            os.path.join(os.path.dirname(dest),
                                         os.readlink(dest))
                        )
                        if old_link_target != os.path.abspath(src):
                            raise BaseException(
                                "Encountered symlink to different "
                                "target: {0}->{1} (Should be {2})".format(
                                    dest, os.readlink(dest), link_target))
                        else:
                            symlinks.append(os.path.join(rel_dir, name))
                            log.info("Symlink already exists {0} -> {1}".
                                     format(link_target, dest))
                else:
                    log.info("Symlinking {0}->{1}".format(link_target, dest))
                    os.symlink(link_target, dest)
                    symlinks.append(os.path.join(rel_dir, name))

            return symlinks

        # Symlink all files in base
        ignore_files.extend(_symlink(''))
        # Symlink all configs in app/etc/modules
        ignore_files.extend(_symlink('app/etc/modules'))
        # Symlink all in app/code/community/VENDOR
        rel_community_dir = os.path.join('app', 'code', 'community')
        src_community_dir = os.path.join(repo_dir, rel_community_dir)

        for vendor_name in os.listdir(src_community_dir):
            rel_vendor_dir = os.path.join(rel_community_dir, vendor_name)
            src_vendor_dir = os.path.join(repo_dir, rel_vendor_dir)
            if os.path.isdir(src_vendor_dir) \
                    and not vendor_name.startswith('.'):
                # Create vendor dir
                dest_vendor_dir = os.path.join(self.magento_dir,
                                               rel_vendor_dir)
                if not os.path.isdir(dest_vendor_dir):
                    os.makedirs(dest_vendor_dir, 0755)
                ignore_files.extend(_symlink(rel_vendor_dir))

        self.write_ignore_file('module.{0}'.format(extension_name),
                               ignore_files)
        self.update_ignore_file()
        # Leave this in a changed state
        log.info("Gitignore updated - repo might be in a modified state")
