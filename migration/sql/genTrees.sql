--------------------------
-----  Gen Trees ---------
--------------------------

with unitFileAttac as
(SELECT UnitFileAttachments.unitid, FileAttachments.AttachmentFileName, FileAttachments.AttachmentNum, FileAttachments.AttachmentPath
FROM 	FileAttachments with (nolock),
		UnitFileAttachments with (nolock)
WHERE  	FileAttachments.AttachmentNum = UnitFileAttachments.AttachmentNum),
 v as
(SELECT   	u.UnitId					as UnitId,
			u.EditorRemarks				as EditorRemarks, 
			u.ForPreview				as ForPreview, 
			u.IsValueUnit				as IsValueUnit,
			u.OldUnitId					as OldUnitId,
			u.RightsCode				as RightsCode, 
			rt.RightsDesc				as RightsDesc,
			u.TS						as TS,
			u.UnitDisplayStatus			as UnitDisplayStatus, 
			uds.DisplayStatusDesc		as DisplayStatusDesc,
			u.UnitStatus				as UnitStatus, 
			us.StatusDesc				as StatusDesc,
			u.UnitType					as UnitType, 
			ut.UnitTypeDesc				as UnitTypeDesc,
			u.UpdateDate				as UpdateDate, 
			u.UpdateUser				as UpdateUser,
			heb.Bibiliography 			as HeBibiliography, 
			eng.Bibiliography 			as EnBibiliography,
			heb.id						as id,
			heb.LocationInMuseum		as LocationInMuseum,
			eng.UnitHeader 				as EnHeader,
			heb.UnitHeader 				as HeHeader,
			heb.UnitHeaderDMSoundex 	as HeUnitHeaderDMSoundex, 
			eng.UnitHeaderDMSoundex 	as EnUnitHeaderDMSoundex,
			heb.UnitText1 				as HeUnitText1,
			heb.UnitText2 				as HeUnitText2,
			eng.UnitText1 				as EnUnitText1,
			eng.UnitText2 				as EnUnitText2,
			STUFF(( SELECT cast(ul.LexiconId as varchar(max)) + ',' FROM dbo.UnitsLexicon ul with (nolock) where ul.UnitId=u.UnitId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') UserLexicon,
			STUFF(( SELECT cast(ufl.AttachmentFileName as nvarchar(max)) + ',' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentFileName,
			STUFF(( SELECT cast(ufl.AttachmentPath as nvarchar(max)) + ',' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentPath,
			STUFF(( SELECT cast(ufl.AttachmentNum as nvarchar(max)) + ',' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentNum
FROM        dbo.Units u with (nolock)
LEFT JOIN	dbo.UnitData heb with (nolock) ON u.UnitId = heb.UnitId and heb.LanguageCode=1
LEFT JOIN	dbo.UnitData eng with (nolock) ON u.UnitId = eng.UnitId and eng.LanguageCode=0
LEFT JOIN dbo.RightsTypes rt with (nolock) ON u.RightsCode = rt.RightsCode
LEFT JOIN dbo.UnitDisplayStatus uds with (nolock) ON u.UnitDisplayStatus = uds.DisplayStatus
LEFT JOIN dbo.UnitStatuses us with (nolock) ON u.UnitStatus = us.UnitStatus
LEFT JOIN dbo.UnitTypes ut with (nolock) ON u.UnitType = ut.UnitType
WHERE     u.UnitType = 4 AND (u.UpdateDate BETWEEN %(since)s AND %(until)s))
select	gt.GenTreeNumber, 
		gt.GenTreeFileId,
		gt.GenTreePath ,
		gt.GenTreeFileName, 
		gt.GenTreeXmlPath,
		gtrs.LastUpdate,
		gtrs.AttemptCount,
		STUFF(( SELECT cast(us.SourceId as varchar(max)) + ',' FROM dbo.UnitSources us with (nolock) where us.UnitId=v.UnitId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') SourceIds,
		v.* 
FROM v with (nolock)
JOIN dbo.GenTree gt with (nolock) on  gt.GenTreeId=v.UnitId
LEFT JOIN GenTreeReportStatus gtrs with (nolock) on gtrs.GenTreeId=gt.GenTreeId;
