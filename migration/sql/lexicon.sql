with unitFileAttac as
(SELECT UnitFileAttachments.unitid, FileAttachments.AttachmentFileName, FileAttachments.AttachmentNum, FileAttachments.AttachmentPath
FROM FileAttachments with (nolock),
	 UnitFileAttachments with (nolock)
WHERE FileAttachments.AttachmentNum = UnitFileAttachments.AttachmentNum),
v as 
(SELECT u.UnitId,u.EditorRemarks, 
		u.ForPreview, u.IsValueUnit,
		u.OldUnitId, u.RightsCode, 
		dbo.RightsTypes.RightsDesc, u.TS,u.UnitDisplayStatus, 
		dbo.UnitDisplayStatus.DisplayStatusDesc, u.UnitStatus, 
		dbo.UnitStatuses.StatusDesc, u.UnitType, 
		dbo.UnitTypes.UnitTypeDesc, u.UpdateDate, 
		u.UpdateUser,
		heb.Bibiliography HeBibiliography, eng.Bibiliography EnBibiliography, 
		heb.id,heb.LocationInMuseum,
		eng.UnitHeader EnHeader, heb.UnitHeader HeHeader,
		heb.UnitHeaderDMSoundex,
		heb.UnitText1 HeUnitText1, heb.UnitText2 HeUnitText2, eng.UnitText1 EnUnitText1, eng.UnitText2 EnUnitText2, 
		STUFF(( SELECT cast(ufl.AttachmentFileName as nvarchar(max)) + ',' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentFileName,
		STUFF(( SELECT cast(ufl.AttachmentPath as nvarchar(max)) + ',' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentPath,
		STUFF(( SELECT cast(ufl.AttachmentNum as nvarchar(max)) + ',' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentNum
		FROM dbo.Units u 
		LEFT JOIN	dbo.UnitData heb with (nolock) ON u.UnitId = heb.UnitId and heb.LanguageCode=1
		LEFT JOIN	dbo.UnitData eng with (nolock) ON u.UnitId = eng.UnitId and eng.LanguageCode=0
		LEFT JOIN dbo.RightsTypes with (nolock) ON u.RightsCode = dbo.RightsTypes.RightsCode 
		LEFT JOIN dbo.UnitDisplayStatus with (nolock) ON u.UnitDisplayStatus = dbo.UnitDisplayStatus.DisplayStatus 
		LEFT JOIN dbo.UnitStatuses with (nolock) ON u.UnitStatus = dbo.UnitStatuses.UnitStatus 
		LEFT JOIN dbo.UnitTypes with (nolock) ON u.UnitType = dbo.UnitTypes.UnitType  
        WHERE u.UnitType = 10 AND (u.UpdateDate BETWEEN %(since)s AND %(until)s OR u.UnitId IN %(unit_ids)s))
		SELECT v.*, 
			STUFF(( SELECT cast(upp.IsPreview as varchar(1)) + ',' FROM dbo.UnitPreviewPics upp with (nolock) where upp.UnitId=v.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') IsPreview, 
			STUFF(( SELECT cast(upp.PictureId as varchar(max)) + ',' FROM dbo.UnitPreviewPics upp with (nolock) where upp.UnitId=v.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureId
		FROM v
