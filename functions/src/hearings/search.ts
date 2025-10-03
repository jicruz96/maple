import { DateTime } from "luxon"
import { db } from "../firebase"
import { createSearchIndexer } from "../search"
import { Hearing } from "../events/types"
import { timeZone } from "../malegislature"

type HearingSearchRecord = {
  id: string
  eventId: number
  title: string
  description?: string
  startsAt: number
  month: string
  year: number
  committeeCode?: string
  committeeName?: string
  locationName?: string
  locationCity?: string
  chairNames?: string[]
  agendaTopics?: string[]
  billNumbers?: string[]
  hasVideo: boolean
}

export const {
  syncToSearchIndex: syncHearingToSearchIndex,
  upgradeSearchIndex: upgradeHearingSearchIndex
} = createSearchIndexer<HearingSearchRecord>({
  sourceCollection: db.collection("events").where("type", "==", "hearing"),
  documentTrigger: "events/{eventId}",
  alias: "hearings",
  idField: "id",
  filter: data => data.type === "hearing",
  schema: {
    fields: [
      { name: "eventId", type: "int32", facet: false },
      { name: "title", type: "string", facet: false },
      { name: "description", type: "string", facet: false, optional: true },
      { name: "startsAt", type: "int64", facet: false },
      { name: "month", type: "string", facet: true },
      { name: "year", type: "int32", facet: true },
      { name: "committeeCode", type: "string", facet: true, optional: true },
      { name: "committeeName", type: "string", facet: true, optional: true },
      { name: "locationName", type: "string", facet: false, optional: true },
      { name: "locationCity", type: "string", facet: false, optional: true },
      { name: "chairNames", type: "string[]", facet: false, optional: true },
      { name: "agendaTopics", type: "string[]", facet: false, optional: true },
      { name: "billNumbers", type: "string[]", facet: false, optional: true },
      { name: "hasVideo", type: "bool", facet: true }
    ],
    default_sorting_field: "startsAt"
  },
  convert: data => {
    const hearing = Hearing.check(data)
    const startsAt = hearing.startsAt.toMillis()
    const schedule = DateTime.fromMillis(startsAt, { zone: timeZone })

    const agendaTopics = hearing.content.HearingAgendas?.map(
      agenda => agenda.Topic
    ).filter(Boolean) as string[]

    const billNumbers = hearing.content.HearingAgendas?.flatMap(agenda =>
      agenda.DocumentsInAgenda.map(doc => doc.BillNumber)
    ).filter(Boolean) as string[]

    const committeeName = hearing.content.Name

    return {
      id: hearing.id,
      eventId: hearing.content.EventId,
      title: committeeName ?? `Hearing ${hearing.content.EventId}`,
      description: hearing.content.Description,
      startsAt,
      month: schedule.toFormat("LLLL"),
      year: schedule.year,
      committeeCode: hearing.content.HearingHost?.CommitteeCode,
      committeeName,
      locationName: hearing.content.Location?.LocationName,
      locationCity: hearing.content.Location?.City,
      chairNames: hearing.committeeChairNames ?? undefined,
      agendaTopics: agendaTopics.length ? agendaTopics : undefined,
      billNumbers: billNumbers.length ? billNumbers : undefined,
      hasVideo: Boolean(hearing.videoURL)
    }
  }
})
