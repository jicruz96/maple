import {
  StyledTabContent,
  StyledTabNav
} from "components/EditProfilePage/StyledEditProfileComponents"
import { FollowContext, OrgFollowStatus } from "components/shared/FollowContext"
import { currentGeneralCourt } from "functions/src/shared"
import { useState } from "react"
import { TabContainer } from "react-bootstrap"
import { useInstantSearch } from "react-instantsearch"
import { Nav } from "../../bootstrap"
import { SearchPage } from "../common"
import { TestimonyHit } from "./TestimonyHit"

export const TestimonySearch = () => {
  const [followStatus, setFollowStatus] = useState<OrgFollowStatus>({})
  const sortOptions = [
    {
      labelKey: "sort_by.newest",
      value: "publishedTestimony/sort/publishedAt:desc"
    },
    {
      labelKey: "sort_by.oldest",
      value: "publishedTestimony/sort/publishedAt:asc"
    },
    {
      labelKey: "sort_by.relevance",
      value: "publishedTestimony/sort/_text_match:desc,publishedAt:desc"
    }
  ]
  return (
    <FollowContext.Provider value={{ followStatus, setFollowStatus }}>
      <SearchPage
        searchType="testimony"
        header={<TabsHeader />}
        hitComponent={TestimonyHit}
        filterConfig={{
          filters: [
            {
              transformItems: items => items.filter(i => i.label !== "private"),
              attribute: "authorDisplayName"
            },
            { attribute: "court" },
            { attribute: "position" },
            { attribute: "billId" },
            { attribute: "authorRole", searchable: false, hidden: true }
          ]
        }}
        sortOptions={sortOptions}
        searchParameters={{
          query_by: "billId,content,authorDisplayName,authorRole"
        }}
        virtualFacetAttributes={[
          "authorDisplayName",
          "court",
          "position",
          "billId",
          "authorRole"
        ]}
        currentRefinementsProps={{ excludedAttributes: ["authorRole"] }}
        initialUiState={{
          [sortOptions[0].value]: {
            refinementList: { court: [String(currentGeneralCourt)] }
          }
        }}
      />
    </FollowContext.Provider>
  )
}

const tabs = ["All", "Individuals", "Organizations"]
type Tab = typeof tabs[number]

const TabsHeader = () => {
  const [key, setKey] = useState<string>("All")
  const { indexUiState, setIndexUiState } = useInstantSearch()

  const onTabClick = (t: Tab) => {
    setKey(t)
    setIndexUiState(prevState => {
      const validRoles = ["user", "organization", "admin"]
      const role =
        t === "Individuals"
          ? ["user"]
          : t === "Organizations"
          ? ["organization"]
          : validRoles
      return {
        ...prevState,
        refinementList: {
          ...prevState.refinementList,
          authorRole: role
        }
      }
    })
  }

  return (
    <>
      <TabContainer activeKey={key} onSelect={(k: any) => setKey(k)}>
        <StyledTabNav>
          {tabs.map((t, i) => (
            <Nav.Item key={t}>
              <Nav.Link
                eventKey={t}
                className={`rounded-top m-0 p-0`}
                onClick={e => onTabClick(t)}
              >
                <p className={`my-0 ${i == 0 ? "" : "mx-4"}`}>{t}</p>
                <hr className={`my-0`} />
              </Nav.Link>
            </Nav.Item>
          ))}
        </StyledTabNav>
        <StyledTabContent></StyledTabContent>
      </TabContainer>
    </>
  )
}
