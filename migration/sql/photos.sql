SELECT cast(PictureId as varchar(max)) as PictureId, PicturePath, PictureFileName 
FROM Pictures with (nolock)
WHERE PictureId IN %(unit_ids)s
