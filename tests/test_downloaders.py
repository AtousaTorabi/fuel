import argparse
import mock
import os
import shutil
import tempfile
from functools import wraps

from numpy.testing import assert_equal, assert_raises

from fuel.downloaders import (binarized_mnist, caltech101_silhouettes,
                              cifar10, cifar100, mnist, svhn)
from fuel.downloaders.base import (download, default_downloader,
                                   filename_from_url, NeedURLPrefix,
                                   ensure_directory_exists)
from picklable_itertools import chain
from six.moves import range

mock_url = 'http://mock.com/mock.data'
mock_filename = 'mock.data'
mock_content = b'mock'


def mock_requests(content_disposition=False, content_length=True):
    def mock_decorator(func):
        @wraps(func)
        @mock.patch('fuel.downloaders.base.requests')
        def wrapper_func(*args, **kwargs):
            mock_requests = args[-1]
            args = args[:-1]
            length = len(mock_content)
            mock_response = mock.Mock()
            mock_response.iter_content = mock.Mock(
                side_effect=lambda s: chain(
                    (mock_content[s * i: s * (i + 1)]
                     for i in range(length // s)),
                    (mock_content[(length // s) * s:],)))
            mock_response.headers = {}
            if content_length:
                mock_response.headers['content-length'] = length
            if content_disposition:
                cd = 'attachment; filename={}'.format(mock_filename)
                mock_response.headers['Content-Disposition'] = cd
            mock_requests.get.return_value = mock_response
            return func(*args, **kwargs)
        return wrapper_func
    return mock_decorator


class TestFilenameFromURL(object):
    @mock_requests()
    def test_no_content_disposition(self):
        assert_equal(filename_from_url(mock_url), mock_filename)

    @mock_requests(content_disposition=True)
    def test_content_disposition(self):
        assert_equal(filename_from_url(mock_url), mock_filename)


class TestDownload(object):
    @mock_requests()
    def test_download_content(self):
        with tempfile.SpooledTemporaryFile() as f:
            download(mock_url, f)
            f.seek(0)
            assert_equal(f.read(), mock_content)

    @mock_requests(content_length=False)
    def test_download_content_no_length(self):
        with tempfile.SpooledTemporaryFile() as f:
            download(mock_url, f)
            f.seek(0)
            assert_equal(f.read(), mock_content)


def test_ensure_directory_exists():
    parent = tempfile.mkdtemp()
    dirpath = os.path.join(parent, 'a', 'b')
    filepath = os.path.join(dirpath, 'f')

    # multiple checks for the same dir are fine
    ensure_directory_exists(dirpath)
    ensure_directory_exists(dirpath)

    assert os.path.exists(dirpath)

    with open(filepath, 'w') as f:
        f.write(' ')

    assert_raises(ensure_directory_exists(filepath))

    shutil.rmtree(dirpath, ignore_errors=True)


def test_mnist():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    mnist.fill_subparser(subparsers.add_parser('mnist'))
    args = parser.parse_args(['mnist'])
    filenames = ['train-images-idx3-ubyte.gz', 'train-labels-idx1-ubyte.gz',
                 't10k-images-idx3-ubyte.gz', 't10k-labels-idx1-ubyte.gz']
    urls = ['http://yann.lecun.com/exdb/mnist/' + f for f in filenames]
    assert_equal(args.filenames, filenames)
    assert_equal(args.urls, urls)
    assert args.func is default_downloader


def test_binarized_mnist():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    binarized_mnist.fill_subparser(subparsers.add_parser('binarized_mnist'))
    args = parser.parse_args(['binarized_mnist'])
    sets = ['train', 'valid', 'test']
    urls = ['http://www.cs.toronto.edu/~larocheh/public/datasets/' +
            'binarized_mnist/binarized_mnist_{}.amat'.format(s) for s in sets]
    filenames = ['binarized_mnist_{}.amat'.format(s) for s in sets]
    assert_equal(args.filenames, filenames)
    assert_equal(args.urls, urls)
    assert args.func is default_downloader


def test_caltech101_silhouettes():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    caltech101_silhouettes.fill_subparser(
        subparsers.add_parser('caltech101_silhouettes'))
    args = parser.parse_args(['caltech101_silhouettes', '16'])
    assert_equal(args.size, 16)
    assert args.func is caltech101_silhouettes.silhouettes_downloader


def test_cifar10():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    cifar10.fill_subparser(subparsers.add_parser('cifar10'))
    args = parser.parse_args(['cifar10'])
    filenames = ['cifar-10-python.tar.gz']
    urls = ['http://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz']
    assert_equal(args.filenames, filenames)
    assert_equal(args.urls, urls)
    assert args.func is default_downloader


def test_cifar100():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    cifar100.fill_subparser(subparsers.add_parser('cifar100'))
    args = parser.parse_args(['cifar100'])
    filenames = ['cifar-100-python.tar.gz']
    urls = ['http://www.cs.toronto.edu/~kriz/cifar-100-python.tar.gz']
    assert_equal(args.filenames, filenames)
    assert_equal(args.urls, urls)
    assert args.func is default_downloader


class TestSVHNDownloader(object):
    def setUp(self):
        self.parser = argparse.ArgumentParser()
        subparsers = self.parser.add_subparsers()
        subparser = subparsers.add_parser('svhn')
        subparser.set_defaults(directory='./', clear=False)
        svhn.fill_subparser(subparser)

    def test_fill_subparser(self):
        args = self.parser.parse_args(['svhn', '1'])
        assert_equal(args.which_format, 1)
        assert args.func is svhn.svhn_downloader

    @mock.patch('fuel.downloaders.svhn.default_downloader')
    def test_svhn_downloader_format_1(self, mock_default_downloader):
        args = self.parser.parse_args(['svhn', '1'])
        args_dict = vars(args)
        func = args_dict.pop('func')
        func(**args_dict)
        mock_default_downloader.assert_called_with(
            directory='./',
            urls=[None] * 3,
            filenames=['train.tar.gz', 'test.tar.gz', 'extra.tar.gz'],
            url_prefix='http://ufldl.stanford.edu/housenumbers/',
            clear=False)

    @mock.patch('fuel.downloaders.svhn.default_downloader')
    def test_svhn_downloader_format_2(self, mock_default_downloader):
        args = self.parser.parse_args(['svhn', '2'])
        args_dict = vars(args)
        func = args_dict.pop('func')
        func(**args_dict)
        mock_default_downloader.assert_called_with(
            directory='./',
            urls=[None] * 3,
            filenames=['train_32x32.mat', 'test_32x32.mat', 'extra_32x32.mat'],
            url_prefix='http://ufldl.stanford.edu/housenumbers/',
            clear=False)


class TestDefaultDownloader(object):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.filepath = os.path.join(self.tempdir, mock_filename)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @mock_requests()
    def test_default_downloader_save_with_filename(self):
        args = dict(directory=self.tempdir, clear=False, urls=[mock_url],
                    filenames=[mock_filename])
        default_downloader(**args)
        with open(self.filepath, 'rb') as f:
            assert_equal(f.read(), mock_content)

    @mock_requests()
    def test_default_downloader_save_no_filename(self):
        args = dict(directory=self.tempdir, clear=False, urls=[mock_url],
                    filenames=[None])
        default_downloader(**args)
        with open(self.filepath, 'rb') as f:
            assert_equal(f.read(), mock_content)

    @mock_requests()
    def test_default_downloader_save_no_url_url_prefix(self):
        args = dict(directory=self.tempdir, clear=False, urls=[None],
                    filenames=[mock_filename], url_prefix=mock_url[:-9])
        default_downloader(**args)
        with open(self.filepath, 'rb') as f:
            assert_equal(f.read(), mock_content)

    @mock_requests()
    def test_default_downloader_save_no_url_no_url_prefix(self):
        args = dict(directory=self.tempdir, clear=False, urls=[None],
                    filenames=[mock_filename])
        assert_raises(NeedURLPrefix, default_downloader, **args)

    @mock_requests()
    def test_default_downloader_save_no_filename_for_url(self):
        args = dict(directory=self.tempdir, clear=False, urls=[mock_url[:-9]],
                    filenames=[None])
        assert_raises(ValueError, default_downloader, **args)

    @mock_requests()
    def test_default_downloader_clear(self):
        file_path = os.path.join(self.tempdir, 'tmp.data')
        open(file_path, 'a').close()
        args = dict(directory=self.tempdir, clear=True, urls=[None],
                    filenames=['tmp.data'])
        default_downloader(**args)
        assert not os.path.isfile(file_path)
