SELECT cast(PictureId as varchar(max)) as PictureId, PicturePath, PictureFileName 
FROM Pictures with (nolock)
WHERE %(all_ids)s=1 OR PictureId IN %(unit_ids)s
