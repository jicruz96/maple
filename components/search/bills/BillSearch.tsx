import { currentGeneralCourt, generalCourts } from "functions/src/shared"
import { useRef } from "react"
import { SearchPage } from "../common"
import { BillHit } from "./BillHit"
import { CurrentRefinementsConnectorParamsItem } from "instantsearch.js/es/connectors/current-refinements/connectCurrentRefinements"

const extractLastSegmentOfRefinements = (
  items: CurrentRefinementsConnectorParamsItem[]
) =>
  items.map(item =>
    item.label != "topics.lvl1"
      ? item
      : {
          ...item,
          label: "Tags",
          refinements: item.refinements.map(({ label, ...rest }) => ({
            ...rest,
            label: label.includes(" > ")
              ? (label.split(" > ").pop() as string)
              : label
          }))
        }
  )

export const BillSearch = () => {
  const now = useRef(new Date().getTime())
  const sortOptions = [
    {
      labelKey: "sort_by.most_recent_testimony",
      value: "bills/sort/latestTestimonyAt:desc"
    },
    {
      labelKey: "sort_by.relevance",
      value: "bills/sort/_text_match:desc,testimonyCount:desc"
    },
    {
      labelKey: "sort_by.testimony_count",
      value: "bills/sort/testimonyCount:desc"
    },
    {
      labelKey: "sort_by.cosponsor_count",
      value: "bills/sort/cosponsorCount:desc"
    },
    {
      labelKey: "sort_by.next_hearing_date",
      value: "bills/sort/nextHearingAt:asc",
      configure: {
        numericRefinements: {
          nextHearingAt: {
            ">=": [now.current]
          } as any
        }
      }
    }
  ]
  return (
    <SearchPage
      searchType="bill"
      hitComponent={BillHit}
      sortOptions={sortOptions}
      initialUiState={{
        [sortOptions[0].value]: {
          refinementList: { court: [String(currentGeneralCourt)] }
        }
      }}
      searchParameters={{
        query_by: "number,title,body",
        exclude_fields: "body"
      }}
      currentRefinementsProps={{
        excludedAttributes: ["nextHearingAt"],
        transformItems: extractLastSegmentOfRefinements
      }}
      filterPanelConfig={{
        menuProps: { attributes: ["topics.lvl0", "topics.lvl1"] },
        filters: [
          {
            attribute: "court",
            transformItems: items =>
              items
                .map(i => ({
                  ...i,
                  label: generalCourts[parseInt(i.value, 10)]?.Name ?? i.label
                }))
                .sort((a, b) => Number(b.value) - Number(a.value))
          },
          { attribute: "currentCommittee" },
          { attribute: "city" },
          { attribute: "primarySponsor" },
          { attribute: "cosponsors" }
        ]
      }}
    />
  )
}
