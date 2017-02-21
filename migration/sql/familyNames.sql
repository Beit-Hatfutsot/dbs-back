--------------------------
-----  Family Names ------
--------------------------
with unitFileAttac as
(SELECT 	UnitFileAttachments.unitid, 
			FileAttachments.AttachmentFileName, 
			FileAttachments.AttachmentNum, 
			FileAttachments.AttachmentPath
FROM 		FileAttachments with (nolock),
			UnitFileAttachments with (nolock)
WHERE  		FileAttachments.AttachmentNum = UnitFileAttachments.AttachmentNum)
SELECT   	u.UnitId 				as UnitId,
			u.EditorRemarks 		as EditorRemarks, 
			u.ForPreview			as ForPreview, 
			u.IsValueUnit			as IsValueUnit,
			u.OldUnitId				as OldUnitId,
			u.RightsCode			as RightsCode, 
			u.TS					as TS,
			u.UnitDisplayStatus		as UnitDisplayStatus, 
			u.UnitStatus			as UnitStatus, 
			u.UnitType				as UnitType, 
			u.UpdateDate			as UpdateDate, 
			u.UpdateUser			as UpdateUser,
			ut.UnitTypeDesc			as UnitTypeDesc,
			uts.StatusDesc			as StatusDesc,
			rt.RightsDesc			as RightsDesc,
			uds.DisplayStatusDesc	as DisplayStatusDesc,
			heb.Bibiliography 		as HeBibiliography, 
			eng.Bibiliography 		as EnBibiliography,
			heb.id					as Id,
			heb.LocationInMuseum	as LocationInMuseum,
			eng.UnitHeader 			as EnHeader,
			heb.UnitHeader 			as HeHeader,
			heb.UnitHeaderDMSoundex as HeUnitHeaderDMSoundex, 
			eng.UnitHeaderDMSoundex as EnUnitHeaderDMSoundex,
			heb.UnitText1 			as HeUnitText1,
			heb.UnitText2 			as HeUnitText2,
			eng.UnitText1 			as EnUnitText1,
			eng.UnitText2 			as EnUnitText2,
			STUFF(( SELECT cast(ul.LexiconId as varchar(max)) + '|' 
					FROM dbo.UnitsLexicon ul 
					where ul.UnitId=u.UnitId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') 	UserLexicon,
			STUFF(( SELECT cast(ufl.AttachmentFileName as nvarchar(max)) + '|'
					FROM unitFileAttac ufl 
					where ufl.UnitId=u.UnitId 
					order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentFileName,
			STUFF(( SELECT cast(ufl.AttachmentPath as nvarchar(max)) + '|'
					FROM unitFileAttac ufl 
					where ufl.UnitId=u.UnitId 
					order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentPath,
			STUFF(( SELECT cast(ufl.AttachmentNum as nvarchar(max)) + '|' 
					FROM unitFileAttac ufl 
					where ufl.UnitId=u.UnitId 
					order by ufl.AttachmentNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') AttachmentNum,
			STUFF(( SELECT cast(dbo.PicturesUnitPics.PictureUnitId as varchar(max)) + '|' 
					FROM dbo.UnitPreviewPics upp 
					JOIN dbo.PicturesUnitPics ON upp.PictureId = dbo.PicturesUnitPics.PictureId AND upp.UnitId <> dbo.PicturesUnitPics.PictureUnitId and upp.UnitId =u.UnitId 
					order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureUnitsIds,
			STUFF(( SELECT  cast(upp.IsPreview as varchar(1)) + '|' 
					FROM dbo.UnitPreviewPics upp 
					where upp.UnitId=u.UnitId 
					order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') IsPreview,
			STUFF(( SELECT  cast(upp.PictureId as varchar(max)) + '|' 
					FROM dbo.UnitPreviewPics upp 
					where upp.UnitId=u.UnitId 
					order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureId,
			-- + Pictures Files Details
			STUFF(( SELECT isnull(cast(P.PicturePath as varchar(max)),'') + '|' 
					FROM dbo.UnitPreviewPics upp left join Pictures P on P.PictureId=upp.PictureId 
					where upp.UnitId=u.UnitId  order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPicturePaths,
			STUFF(( SELECT isnull(cast(P.PictureFileName as varchar(max)),'') + '|' 
					FROM dbo.UnitPreviewPics upp 
					left join Pictures P on P.PictureId=upp.PictureId 
					where upp.UnitId=u.UnitId
					order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPictureFileNames
FROM        dbo.Units u
LEFT JOIN	dbo.UnitData heb ON u.UnitId = heb.UnitId and heb.LanguageCode=1
LEFT JOIN	dbo.UnitData eng ON u.UnitId = eng.UnitId and eng.LanguageCode=0
LEFT JOIN 	dbo.RightsTypes rt ON u.RightsCode = rt.RightsCode
LEFT JOIN 	dbo.UnitDisplayStatus uds ON u.UnitDisplayStatus = uds.DisplayStatus
LEFT JOIN 	dbo.UnitStatuses uts ON u.UnitStatus = uts.UnitStatus
LEFT JOIN 	dbo.UnitTypes ut ON u.UnitType = ut.UnitType
WHERE     u.UnitType = 6 AND (u.UpdateDate BETWEEN %(since)s AND %(until)s OR u.UnitId IN %(unit_ids)s)
