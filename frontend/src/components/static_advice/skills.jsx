import React from 'react'

import picto from 'images/advices/picto-specific-to-job.png'

import {AdviceDetail, AdviceSection, StaticAdviceCardBase,
  StaticAdvicePage} from 'components/static_advice'
import {TestimonialCard, TestimonialStaticSection} from 'components/testimonials'


const adviceId = 'competences'


const name = 'Compétences clés'


class Page extends React.Component {
  render() {
    return <StaticAdvicePage
      adviceId={adviceId}
      title="Identifiez les compétences clés pour booster votre carrière avec Bob">
      <AdviceSection
        adviceId={adviceId} title="anticiper l'avenir de votre métier">
        <AdviceDetail>
          Un <strong>diagnostic</strong> pour analyser des <strong>perspectives d'avenir </strong>
          offertes par votre métier.
        </AdviceDetail>
        <AdviceDetail>
          Une liste des <strong>compétences</strong> qui peuvent faire la différence dans votre
          domaine.
        </AdviceDetail>
        <AdviceDetail>
          Des idées de <strong>formations</strong> à suivre pour vous épanouir et booster
          votre <strong>carrière</strong>.
        </AdviceDetail>
      </AdviceSection>
      <TestimonialStaticSection visualElement="skills">
        <TestimonialCard
          author={{age: 22, isMan: true, jobName: 'Agent de voyage', name: 'Ludovic'}}
          isLong={true}>
          Grâce à Bob&nbsp;! Voir qu'il n'y a jamais d'impasse&nbsp;!
        </TestimonialCard>
        <TestimonialCard
          author={{age: 46, isMan: true, jobName: 'Commercial', name: 'Charles'}} isLong={true}>
          Je suis un nouvel utilisateur de votre outil <strong>Bob Emploi</strong> et je le trouve
          très utile, très pertinent. Tout simplifier et résumer en une
          <strong>statistique</strong> est en effet une idée brillante.
        </TestimonialCard>
        <TestimonialCard
          author={{age: 38, jobName: 'Chargée de communication', name: 'Émilie'}}
          isLong={true}>
          Le principe est très sympa. Et même quand on est autonome comme je le suis dans
          ma <strong>recherche d'emploi</strong>, cela apporte une vision extérieure
          très importante.
        </TestimonialCard>
      </TestimonialStaticSection>
    </StaticAdvicePage>
  }
}


class StaticAdviceCard extends React.Component {
  render() {
    return <StaticAdviceCardBase picto={picto} name={name} {...this.props} >
      Les <strong>compétences clés</strong> pour booster votre carrière
    </StaticAdviceCardBase>
  }
}


export default {Page, StaticAdviceCard, adviceId, name}
