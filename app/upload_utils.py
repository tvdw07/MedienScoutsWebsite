import os
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from flask import current_app
from werkzeug.utils import secure_filename


PROFILE_PICTURE_FOLDER = 'profile_pictures'
TICKET_ATTACHMENT_FOLDER = 'tickets'

PROFILE_PICTURE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
TICKET_ATTACHMENT_EXTENSIONS = {'jpg', 'jpeg', 'png'}


class UploadValidationError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _resolve_upload_root():
    upload_root = current_app.config.get('UPLOAD_ROOT', 'uploads')
    if os.path.isabs(upload_root):
        return upload_root
    return os.path.join(current_app.instance_path, upload_root)


def get_upload_folder(*parts):
    return os.path.join(_resolve_upload_root(), *parts)


def ensure_upload_folder(*parts):
    folder = get_upload_folder(*parts)
    os.makedirs(folder, exist_ok=True)
    return folder


def normalize_stored_filename(value):
    if not value:
        return None
    return os.path.basename(str(value).replace('\\', '/'))


def _file_size(file_storage):
    stream = file_storage.stream
    current_position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(current_position)
    return size


def _extension_matches_format(extension, detected_format):
    if extension in {'jpg', 'jpeg'}:
        return detected_format == 'jpeg'
    return detected_format == extension


def _validate_image(file_storage, allowed_extensions, max_size):
    original_filename = secure_filename(file_storage.filename or '')
    extension = Path(original_filename).suffix.lower().lstrip('.')

    if not original_filename or not extension or extension not in allowed_extensions:
        raise UploadValidationError('Ungültiger Dateityp.')

    if _file_size(file_storage) > max_size:
        raise UploadValidationError('Datei ist zu groß.', status_code=413)

    stream = file_storage.stream
    stream.seek(0)
    try:
        with Image.open(stream) as image:
            image.verify()
        stream.seek(0)
        with Image.open(stream) as image:
            image.load()
            detected_format = (image.format or '').lower()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UploadValidationError('Ungültiges Bild.') from exc
    finally:
        stream.seek(0)

    if not detected_format or not _extension_matches_format(extension, detected_format):
        raise UploadValidationError('Bildformat stimmt nicht mit der Dateiendung überein.')

    return extension, original_filename


def save_validated_image_upload(file_storage, *, folder_name, allowed_extensions, max_size):
    folder = ensure_upload_folder(folder_name)
    extension, original_filename = _validate_image(file_storage, allowed_extensions, max_size)

    stored_filename = f'{uuid.uuid4()}.{extension}'
    destination = os.path.join(folder, stored_filename)
    file_storage.stream.seek(0)
    file_storage.save(destination)
    return stored_filename, original_filename


def delete_stored_upload(folder_name, stored_filename):
    normalized_filename = normalize_stored_filename(stored_filename)
    if not normalized_filename:
        return False

    folder = get_upload_folder(folder_name)
    file_path = os.path.join(folder, normalized_filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False


def save_profile_picture(file_storage):
    stored_filename, original_filename = save_validated_image_upload(
        file_storage,
        folder_name=current_app.config.get('PROFILE_PICTURE_FOLDER', PROFILE_PICTURE_FOLDER),
        allowed_extensions=PROFILE_PICTURE_EXTENSIONS,
        max_size=current_app.config['MAX_PROFILE_IMAGE_SIZE'],
    )

    folder = get_upload_folder(current_app.config.get('PROFILE_PICTURE_FOLDER', PROFILE_PICTURE_FOLDER))
    file_path = os.path.join(folder, stored_filename)

    try:
        with Image.open(file_path) as image:
            image.thumbnail((800, 800))
            image.save(file_path)
    except Exception as exc:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise UploadValidationError('Profilbild konnte nicht verarbeitet werden.') from exc

    return stored_filename, original_filename


def save_ticket_attachment(file_storage):
    return save_validated_image_upload(
        file_storage,
        folder_name=current_app.config.get('TICKET_ATTACHMENT_FOLDER', TICKET_ATTACHMENT_FOLDER),
        allowed_extensions=TICKET_ATTACHMENT_EXTENSIONS,
        max_size=current_app.config['MAX_TICKET_ATTACHMENT_SIZE'],
    )
