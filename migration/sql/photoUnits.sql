with unitFileAttac as
(SELECT 	UnitFileAttachments.unitid, 
			FileAttachments.AttachmentFileName, 
			FileAttachments.AttachmentNum, 
			FileAttachments.AttachmentPath
 FROM 		FileAttachments with (nolock),
			UnitFileAttachments with (nolock)
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
FROM        dbo.Units u with (nolock)
LEFT JOIN	dbo.UnitData heb with (nolock) ON u.UnitId = heb.UnitId and heb.LanguageCode=1
LEFT JOIN	dbo.UnitData eng with (nolock) ON u.UnitId = eng.UnitId and eng.LanguageCode=0
LEFT JOIN dbo.RightsTypes rt with (nolock) ON u.RightsCode = rt.RightsCode
LEFT JOIN dbo.UnitDisplayStatus uds with (nolock) ON u.UnitDisplayStatus = uds.DisplayStatus
LEFT JOIN dbo.UnitStatuses us with (nolock) ON u.UnitStatus = us.UnitStatus
LEFT JOIN dbo.UnitTypes ut with (nolock) ON u.UnitType = ut.UnitType
WHERE   u.UnitType = 1 AND (u.UpdateDate BETWEEN %(since)s AND %(until)s OR u.UnitId IN %(unit_ids)s))
SELECT  pic.*,
		--UnitSources
		STUFF(( SELECT cast(us.SourceId as varchar(max)) + '|' FROM dbo.UnitSources us with (nolock) where us.UnitId=pic.UnitId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureSources,
		--UnitPreviewPics
		STUFF(( SELECT cast(dbo.PicturesUnitPics.PictureUnitId as varchar(max)) FROM dbo.UnitPreviewPics upp with (nolock) JOIN dbo.PicturesUnitPics with (nolock) ON upp.PictureId = dbo.PicturesUnitPics.PictureId AND upp.UnitId =pic.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPictureUnitsId,
		STUFF(( SELECT cast(upp.IsPreview as varchar(1)) FROM dbo.UnitPreviewPics upp with (nolock) where upp.UnitId=pic.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') IsPreview,
		STUFF(( SELECT cast(upp.PictureId as varchar(max)) FROM dbo.UnitPreviewPics upp with (nolock) where upp.UnitId=pic.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPictureId,
		-- + Pictures Files Details
		STUFF(( SELECT isnull(cast(P.PicturePath as varchar(max)), '') + '|' FROM dbo.UnitPreviewPics upp with (nolock) left join Pictures P with (nolock) on P.PictureId=upp.PictureId where upp.UnitId=pic.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPicturePaths,
		STUFF(( SELECT  isnull(cast(P.PictureFileName as varchar(max)), '') FROM dbo.UnitPreviewPics upp with (nolock) left join Pictures P with (nolock) on P.PictureId=upp.PictureId where upp.UnitId=pic.UnitId order by upp.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PrevPictureFileNames,
		-- UnitPlaces
		STUFF(( SELECT cast(upp.PlaceId as varchar(max)) + '|' FROM dbo.UnitPlaces upp with (nolock) where upp.UnitId=pic.UnitId order by upp.PlaceId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PlaceIds,
		/*STUFF(( SELECT cast(upp.PlaceDescriptionTypeCode as varchar(max)) + '|' FROM dbo.UnitPlaces upp with (nolock) where upp.UnitId=pic.UnitId order by upp.PlaceId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PlaceTypeCodes,*/
		/*STUFF(( SELECT cast(upd.PlaceDescriptionTypeDesc as nvarchar(max)) + '|' FROM dbo.UnitPlaces up with (nolock) join dbo.PlaceDescriptionTypesData upd with (nolock) on upd.PlaceDescriptionTypeCode=up.PlaceDescriptionTypeCode where up.UnitId=pic.UnitId and upd.LanguageCode=1 order by up.PlaceId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') HePlaceTypeCodesDesc,*/
		/*STUFF(( SELECT cast(upd.PlaceDescriptionTypeDesc as nvarchar(max)) + '|' FROM dbo.UnitPlaces up with (nolock) join dbo.PlaceDescriptionTypesData upd with (nolock) on upd.PlaceDescriptionTypeCode=up.PlaceDescriptionTypeCode where up.UnitId=pic.UnitId and upd.LanguageCode=0 order by up.PlaceId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') EnPlaceTypeCodesDesc,*/
		-- PIctureReceived
		STUFF(( SELECT cast(pu.PictureReceiveUnitId as varchar(max)) + '|' FROM dbo.PictureUnits pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureReceiveUnitId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PIctureReceivedIds,
		-- UnitPersonalities
		STUFF(( SELECT isnull(cast(pu.PersonalityId as varchar(max)), '') + '|' FROM dbo.UnitPersonalities pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PersonalityIds,
		/*STUFF(( SELECT cast(pu.PersonTypeCode as varchar(max)) + '|' FROM dbo.UnitPersonalities pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PersonalityTypes,
		STUFF(( SELECT cast(ptd.PersonTypeDesc as nvarchar(max)) + '|' FROM dbo.UnitPersonalities pu with (nolock) join dbo.PersonTypesData ptd with (nolock) on ptd.PersonTypeCode=pu.PersonTypeCode  where pu.UnitId=pic.UnitId and ptd.LanguageCode=1 order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') HePersonalityTypeDesc,
		STUFF(( SELECT cast(ptd.PersonTypeDesc as nvarchar(max)) + '|' FROM dbo.UnitPersonalities pu with (nolock) join dbo.PersonTypesData ptd with (nolock) on ptd.PersonTypeCode=pu.PersonTypeCode  where pu.UnitId=pic.UnitId and ptd.LanguageCode=0 order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') EnPersonalityTypeDesc,
		STUFF(( SELECT cast(pu.PerformerType as varchar(max)) + '|' FROM dbo.UnitPersonalities pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PerformerTyps,
		STUFF(( SELECT cast(ptd.PerformerTypeDesc as nvarchar(max)) + '|' FROM dbo.UnitPersonalities pu with (nolock) join dbo.PerformersTypesData ptd with (nolock) on ptd.PerformerType=pu.PerformerType where pu.UnitId=pic.UnitId  and ptd.LanguageCode=1 order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') HePerformerTypeDec,
		STUFF(( SELECT cast(ptd.PerformerTypeDesc as nvarchar(max)) + '|' FROM dbo.UnitPersonalities pu with (nolock) join dbo.PerformersTypesData ptd with (nolock) on ptd.PerformerType=pu.PerformerType where pu.UnitId=pic.UnitId  and ptd.LanguageCode=0 order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') EnPerformerTypeDec,*/
		STUFF(( SELECT isnull(cast(pu.OrderBy as varchar(max)), '') + '|' FROM dbo.UnitPersonalities pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PersonalityId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') OrderBy,
		-- Pictures
		STUFF(( SELECT isnull(cast(pu.PicId as varchar(max)), '')  + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PicId,
		STUFF(( SELECT isnull(cast(pu.PictureId as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureId,
		STUFF(( SELECT isnull(cast(pu.OldPictureNumber as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') OldPictureNumbers,
		STUFF(( SELECT isnull(cast(pu.PictureTypeCode as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureTypeCodes,
		STUFF(( SELECT isnull(cast(ptd.PictureTypeDesc as nvarchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) join dbo.PictureTypesData ptd with (nolock) on ptd.PictureTypeCode=pu.PictureTypeCode where pu.PictureUnitId=pic.UnitId and ptd.LanguageCode=1 order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') HePictureTypeDesc,
		STUFF(( SELECT isnull(cast(ptd.PictureTypeDesc as nvarchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) join dbo.PictureTypesData ptd with (nolock) on ptd.PictureTypeCode=pu.PictureTypeCode where pu.PictureUnitId=pic.UnitId and ptd.LanguageCode=0 order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') EnPictureTypeDesc,
		STUFF(( SELECT isnull(cast(pu.Resolution as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') Resolutions,
		STUFF(( SELECT isnull(cast(pu.NegativeNumber as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') NegativeNumbers,
		STUFF(( SELECT isnull(cast(pu.PictureLocation as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureLocations,
		STUFF(( SELECT isnull(cast(pu.LocationCode as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') LocationCode,
		STUFF(( SELECT isnull(cast(pu.ToScan as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') ToScan,
		STUFF(( SELECT isnull(cast(pu.ForDisplay as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') ForDisplay,
		STUFF(( SELECT isnull(cast(pu.IsPreview as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') IsPreview,
		STUFF(( SELECT isnull(cast(pu.IsLandscape as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) where pu.PictureUnitId=pic.UnitId order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') IsLandscape,
		-- Pictures Files Details
		STUFF(( SELECT isnull(cast(P.PicturePath as varchar(max)), '') FROM dbo.PicturesUnitPics pu with (nolock) left join Pictures P with (nolock) on P.PictureId=pu.PictureId where pu.PictureUnitId=pic.UnitId and pu.PictureId is not null order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PicturePaths,
		STUFF(( SELECT isnull(cast(P.PictureFileName as varchar(max)), '') + '|' FROM dbo.PicturesUnitPics pu with (nolock) left join Pictures P with (nolock) on P.PictureId=pu.PictureId where pu.PictureUnitId=pic.UnitId and pu.PictureId is not null order by pu.PictureId for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PictureFileNames,
		--UnitPeriod
		STUFF(( SELECT isnull(cast(pu.PeriodNum as varchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PeriodNum,
		STUFF(( SELECT isnull(cast(pu.PeriodTypeCode as varchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PeriodTypeCode,
		STUFF(( SELECT isnull(cast(ptd.PeriodTypeDesc as nvarchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) join dbo.PeriodTypesData ptd with (nolock) on ptd.PeriodTypeCode=pu.PeriodTypeCode where pu.UnitId=pic.UnitId and ptd.LanguageCode=1 order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') HePeriodTypeDesc,
		STUFF(( SELECT isnull(cast(ptd.PeriodTypeDesc as nvarchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) join dbo.PeriodTypesData ptd with (nolock) on ptd.PeriodTypeCode=pu.PeriodTypeCode where pu.UnitId=pic.UnitId and ptd.LanguageCode=0 order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') EnPeriodTypeDesc,
		STUFF(( SELECT isnull(cast(pu.PeriodDateTypeCode as varchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PeriodDateTypeCode,
		STUFF(( SELECT isnull(cast(ptd.PeriodDateTypeDesc as nvarchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) join dbo.PeriodDateTypesData ptd with (nolock) on ptd.PeriodDateTypeCode=pu.PeriodDateTypeCode where pu.UnitId=pic.UnitId and ptd.LanguageCode=1 order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') HePeriodDateTypeDesc,
		STUFF(( SELECT isnull(cast(ptd.PeriodDateTypeDesc as nvarchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) join dbo.PeriodDateTypesData ptd with (nolock) on ptd.PeriodDateTypeCode=pu.PeriodDateTypeCode where pu.UnitId=pic.UnitId and ptd.LanguageCode=0 order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') EnPeriodDateTypeDesc,
		STUFF(( SELECT isnull(cast(pu.PeriodStartDate as varchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PeriodStartDate,
		STUFF(( SELECT isnull(cast(pu.PeriodEndDate as varchar(max)), '') + '|' FROM dbo.UnitPeriods pu with (nolock) where pu.UnitId=pic.UnitId order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') PeriodEndDate,
		STUFF(( SELECT isnull(cast(pu.PeriodDesc as nvarchar(max)), '') + '|' FROM dbo.UnitPeriodsData pu with (nolock) where pu.UnitId=pic.UnitId and pu.LanguageCode=1 order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') HePeriodDesc,
		STUFF(( SELECT isnull(cast(pu.PeriodDesc as nvarchar(max)), '') + '|' FROM dbo.UnitPeriodsData pu with (nolock) where pu.UnitId=pic.UnitId and pu.LanguageCode=0 order by pu.PeriodNum for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') EnPeriodDesc,
		-- Exhabitions
		STUFF(( SELECT isnull(cast(ex.[ExhibitionId] as nvarchar(max)), '') + '|' FROM dbo.ExhibitionLinkedUnits ex with (nolock) where ex.[LinkedUnitId]=pic.UnitId order by ex.[ExhibitionId] for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') ExhibitionId,
		STUFF(( SELECT isnull(cast(ex.IsPreview as nvarchar(max)), '') + '|' FROM dbo.ExhibitionLinkedUnits ex with (nolock) where ex.[LinkedUnitId]=pic.UnitId order by ex.[ExhibitionId] for XML PATH(''),Type).value('.','NVARCHAR(MAX)'),1,0,'') ExhibitionIsPreview
FROM v pic
