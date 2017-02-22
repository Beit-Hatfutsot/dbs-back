--------------------------
-----  Places ------------
--------------------------
with unitFileAttac as
(SELECT 	UnitFileAttachments.unitid, 
			FileAttachments.AttachmentFileName, 
			FileAttachments.AttachmentNum, 
			FileAttachments.AttachmentPath
FROM 		FileAttachments with (nolock),UnitFileAttachments with (nolock)
WHERE  		FileAttachments.AttachmentNum = UnitFileAttachments.AttachmentNum),
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
			STUFF(( SELECT cast(ul.LexiconId as varchar(max)) + '|' FROM dbo.UnitsLexicon ul with (nolock) where ul.UnitId=u.UnitId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') UserLexicon,
			STUFF(( SELECT cast(ufl.AttachmentFileName as nvarchar(max)) + '|' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentFileName,
			STUFF(( SELECT cast(ufl.AttachmentPath as nvarchar(max)) + '|' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentPath,
			STUFF(( SELECT cast(ufl.AttachmentNum as nvarchar(max)) + '|' FROM unitFileAttac ufl with (nolock) where ufl.UnitId=u.UnitId order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentNum
--dbo.PlaceTypesData.PlaceTypeDesc,dbo.Places.PlaceTypeCode,
FROM        dbo.Units u with (nolock)
LEFT JOIN	dbo.UnitData heb 			with (nolock) ON u.UnitId = heb.UnitId and heb.LanguageCode=1
LEFT JOIN	dbo.UnitData eng 			with (nolock) ON u.UnitId = eng.UnitId and eng.LanguageCode=0
LEFT JOIN 	dbo.RightsTypes rt 			with (nolock) ON u.RightsCode = rt.RightsCode
LEFT JOIN 	dbo.UnitDisplayStatus uds 	with (nolock) ON u.UnitDisplayStatus = uds.DisplayStatus
LEFT JOIN 	dbo.UnitStatuses us			with (nolock) ON u.UnitStatus = us.UnitStatus
LEFT JOIN 	dbo.UnitTypes ut			with (nolock) ON u.UnitType = ut.UnitType
WHERE     u.UnitType = 5 AND (u.UpdateDate BETWEEN %(since)s AND %(until)s OR u.UnitId IN %(unit_ids)s))
SELECT		plcdheb.PlaceTypeDesc 			as HePlaceTypeDesc,
			plcdeng.PlaceTypeDesc 			as EnPlaceTypeDesc,
			plc.PlaceTypeCode     			as PlaceTypeCode,
			plc.PlaceParentId	  			as PlaceParentId,
			plcd_parentheb.PlaceTypeDesc 	as PlaceParentTypeCodeDesc,
			plcd_parentheb.PlaceTypeDesc 	as HePlaceParentTypeCodeDesc,
			plcd_parenteng.PlaceTypeDesc 	as EnPlaceParentTypeCodeDesc,
			STUFF(( SELECT cast(dbo.PicturesUnitPics.PictureUnitId as varchar(max)) + '|' FROM dbo.UnitPreviewPics upp JOIN dbo.PicturesUnitPics ON upp.PictureId = dbo.PicturesUnitPics.PictureId AND upp.UnitId <> dbo.PicturesUnitPics.PictureUnitId and upp.UnitId =v.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureUnitsIds,
			STUFF(( SELECT cast(upp.IsPreview as varchar(1)) + '|' FROM dbo.UnitPreviewPics upp where upp.UnitId=v.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') IsPreview,
			STUFF(( SELECT cast(upp.PictureId as varchar(max)) + '|' FROM dbo.UnitPreviewPics upp where upp.UnitId=v.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureId,
			-- + Pictures Files Details
			STUFF(( SELECT isnull(cast(P.PicturePath as varchar(max)),'') + '|' FROM dbo.UnitPreviewPics upp left join Pictures P on P.PictureId=upp.PictureId where upp.UnitId=v.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPicturePaths,
			STUFF(( SELECT isnull(cast(P.PictureFileName as varchar(max)),'') + '|' FROM dbo.UnitPreviewPics upp left join Pictures P on P.PictureId=upp.PictureId where upp.UnitId=v.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPictureFileNames
,v.*
FROM  		dbo.Places plc with (nolock)
JOIN  		v on plc.PlaceId = v.UnitId
LEFT JOIN 	dbo.PlaceTypesData plcdheb with (nolock) ON plc.PlaceTypeCode = plcdheb.PlaceTypeCode AND 1=plcdheb.LanguageCode
LEFT JOIN 	dbo.PlaceTypesData plcdeng with (nolock) ON plc.PlaceTypeCode = plcdeng.PlaceTypeCode AND 0=plcdeng.LanguageCode
LEFT JOIN 	dbo.Places plc_parent with (nolock) ON  plc_parent.PlaceId=plc.PlaceParentId
LEFT JOIN 	dbo.PlaceTypesData plcd_parentheb with (nolock) ON plc_parent.PlaceTypeCode = plcd_parentheb.PlaceTypeCode AND 1=plcd_parentheb.LanguageCode
LEFT JOIN 	dbo.PlaceTypesData plcd_parenteng with (nolock) ON plc_parent.PlaceTypeCode = plcd_parenteng.PlaceTypeCode AND 0=plcd_parenteng.LanguageCode
ORDER BY 	v.UnitId;
